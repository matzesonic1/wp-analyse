"""Tests für die Orchestrierung der Analysen und Alarmverarbeitung."""

from datetime import UTC, datetime, timedelta

import pandas as pd

from wpanalyse.alarm import AlarmManager
from wpanalyse.analyse.effizienz import EffizienzErgebnis
from wpanalyse.analyse.komfort import KomfortErgebnis
from wpanalyse.analyse.spreizung import SpreizungErgebnis
from wpanalyse.analyse.taktung import TaktungErgebnis
from wpanalyse.config import Config
from wpanalyse.models import Befund, Bewertung
from wpanalyse.monitoring import pruefe_und_melde


class FakeSpeicher:
    """Liefert Messwerte und zeichnet den angefragten Zeitraum auf."""

    def __init__(self, daten: pd.DataFrame):
        self.daten = daten
        self.zeitraum = None

    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        self.zeitraum = (von, bis)
        return self.daten


class FakeAlarmManager:
    """Sammelt die vollständigen Befundstände ohne Benachrichtigung."""

    def __init__(self):
        self.aufrufe = []

    def verarbeite(self, befunde):
        self.aufrufe.append(list(befunde))


class FakeMelder:
    """Sammelt Alarmmeldungen für Tests des echten Alarmmanagers."""

    def __init__(self):
        self.nachrichten = []

    def sende(self, nachricht: str) -> None:
        self.nachrichten.append(nachricht)


def _vollstaendige_daten() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=31 * 48 + 1, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "verdichter_an": [True] * len(index),
            "vorlauf_c": [35.0] * len(index),
            "ruecklauf_c": [30.0] * len(index),
            "waerme_kwh": [1.0] * len(index),
            "strom_kwh": [0.3] * len(index),
            "aussen_c": [0.0] * len(index),
            "heizstab_an": [False] * len(index),
            "raum_wohnzimmer_c": [20.0] * len(index),
            "raum_bad_c": [22.0] * len(index),
            "raum_schlafzimmer_c": [18.0] * len(index),
        },
        index=index,
    )


def test_liest_zeitraum_fuehrt_analysen_zusammen_und_meldet_einmal(monkeypatch):
    von = datetime(2026, 1, 1, tzinfo=UTC)
    bis = von + timedelta(days=31)
    speicher = FakeSpeicher(_vollstaendige_daten())
    alarm_manager = FakeAlarmManager()
    erwartete_befunde = [
        Befund("A1", Bewertung.WARNUNG, "Taktung"),
        Befund("A2", Bewertung.WARNUNG, "Effizienz"),
        Befund("A4", Bewertung.WARNUNG, "Heizstab"),
        Befund("A3", Bewertung.HINWEIS, "Spreizung"),
        Befund("A5", Bewertung.WARNUNG, "Komfort"),
        Befund("A6", Bewertung.KRITISCH, "Kälte"),
        Befund("KOMFORT", Bewertung.HINWEIS, "Abgleich"),
    ]

    monkeypatch.setattr(
        "wpanalyse.monitoring.analysiere_taktung",
        lambda df, cfg: TaktungErgebnis(21.0, 5.0, Bewertung.WARNUNG, [erwartete_befunde[0]]),
    )
    monkeypatch.setattr(
        "wpanalyse.monitoring.analysiere_effizienz",
        lambda df, cfg: EffizienzErgebnis(
            {}, Bewertung.WARNUNG, [erwartete_befunde[1], erwartete_befunde[2]]
        ),
    )
    monkeypatch.setattr(
        "wpanalyse.monitoring.analysiere_spreizung",
        lambda df, cfg: SpreizungErgebnis(8.0, Bewertung.HINWEIS, [erwartete_befunde[3]]),
    )
    monkeypatch.setattr(
        "wpanalyse.monitoring.analysiere_komfort",
        lambda df, cfg: KomfortErgebnis({}, None, None, Bewertung.KRITISCH, erwartete_befunde[4:]),
    )

    befunde = pruefe_und_melde(speicher, alarm_manager, Config(), von, bis)

    assert speicher.zeitraum == (von, bis)
    assert befunde == erwartete_befunde
    assert alarm_manager.aufrufe == [erwartete_befunde]


def test_fehlende_optionale_felder_machen_regeln_nicht_auswertbar():
    von = datetime(2026, 1, 1, tzinfo=UTC)
    bis = von + timedelta(hours=1)
    index = pd.date_range(von, periods=2, freq="30min")
    speicher = FakeSpeicher(pd.DataFrame({"verdichter_an": [False, False]}, index=index))
    melder = FakeMelder()
    alarm_manager = AlarmManager(melder)
    alarm_manager.verarbeite([Befund("A4", Bewertung.WARNUNG, "Heizstab aktiv")], von)

    befunde = pruefe_und_melde(speicher, alarm_manager, Config(), von, bis)

    assert "A4" in {befund.regel_id for befund in befunde}
    assert any("nicht auswertbar" in befund.text for befund in befunde)
    assert not any(nachricht.startswith("Entwarnung: A4") for nachricht in melder.nachrichten)


def test_uebergibt_auch_leeren_befundstand_einmal(monkeypatch):
    von = datetime(2026, 1, 1, tzinfo=UTC)
    bis = von + timedelta(days=31)
    speicher = FakeSpeicher(_vollstaendige_daten())
    alarm_manager = FakeAlarmManager()
    monkeypatch.setattr(
        "wpanalyse.monitoring.analysiere_taktung",
        lambda df, cfg: TaktungErgebnis(0.0, 60.0, Bewertung.OK),
    )
    monkeypatch.setattr(
        "wpanalyse.monitoring.analysiere_effizienz",
        lambda df, cfg: EffizienzErgebnis({}, Bewertung.OK),
    )
    monkeypatch.setattr(
        "wpanalyse.monitoring.analysiere_spreizung",
        lambda df, cfg: SpreizungErgebnis(5.0, Bewertung.OK),
    )
    monkeypatch.setattr(
        "wpanalyse.monitoring.analysiere_komfort",
        lambda df, cfg: KomfortErgebnis({}, None, None, Bewertung.OK),
    )

    assert pruefe_und_melde(speicher, alarm_manager, Config(), von, bis) == []
    assert alarm_manager.aufrufe == [[]]
