"""Tests für Raumtemperaturanteile, Komfortbefunde und Datenlücken."""

import pandas as pd

from wpanalyse.analyse.komfort import analysiere_komfort
from wpanalyse.config import Config
from wpanalyse.models import Bewertung
from wpanalyse.simulation import simuliere


def test_anteil_unter_soll_berechnet_mehrere_raeume_und_findet_kaeltesten():
    """Die Analyse vergleicht mehrere Räume und identifiziert den kältesten."""
    index = pd.date_range("2026-01-01", periods=4, freq="min", tz="UTC")
    df = pd.DataFrame(
        {
            "raum_wohnzimmer_c": [18.0, 20.0, 20.0, 20.0],
            "raum_buero_c": [17.5, 17.5, 17.5, 17.5],
        },
        index=index,
    )
    cfg = Config(raum_soll_c={"wohnzimmer": 20.0, "buero": 20.0})

    erg = analysiere_komfort(df, cfg)

    assert erg.anteil_unter_soll == {"wohnzimmer": 0.333, "buero": 1.0}
    assert erg.kaeltester_raum == "buero"
    assert erg.kaelteste_mitteltemperatur_c == 17.5
    assert erg.bewertung == Bewertung.HINWEIS
    assert any("hydraulischen Abgleich" in befund.text for befund in erg.befunde)


def test_a5_loest_erst_nach_mehr_als_zwei_stunden_aus():
    """Die Komfortwarnung entsteht erst nach Überschreiten der Zeitgrenze."""
    index = pd.date_range("2026-01-01", periods=182, freq="min", tz="UTC")
    df = pd.DataFrame({"raum_wohnzimmer_c": [18.0] * len(index)}, index=index)
    cfg = Config(raum_soll_c={"wohnzimmer": 20.0})

    genau_zwei_stunden = analysiere_komfort(df.iloc[:121], cfg)
    mehr_als_zwei_stunden = analysiere_komfort(df, cfg)

    assert "A5" not in {befund.regel_id for befund in genau_zwei_stunden.befunde}
    assert "A5" in {befund.regel_id for befund in mehr_als_zwei_stunden.befunde}
    assert mehr_als_zwei_stunden.bewertung == Bewertung.WARNUNG


def test_a6_ist_kritisch_und_fehlende_sollwerte_verhindern_a6_nicht():
    """Kritische Kälte gilt auch für Räume ohne konfigurierten Sollwert."""
    index = pd.date_range("2026-01-01", periods=3, freq="min", tz="UTC")
    df = pd.DataFrame({"raum_gaestezimmer_c": [18.0, 16.9, 18.0]}, index=index)

    erg = analysiere_komfort(df, Config())

    assert erg.bewertung == Bewertung.KRITISCH
    assert [befund.regel_id for befund in erg.befunde] == ["A6"]
    assert erg.anteil_unter_soll == {}

    grenzwert_df = pd.DataFrame(
        {"raum_gaestezimmer_c": [17.0, 18.0]},
        index=index[:2],
    )
    grenzwert_erg = analysiere_komfort(grenzwert_df, Config())
    assert "A6" not in {befund.regel_id for befund in grenzwert_erg.befunde}


def test_nan_und_unregelmaessige_zeitabstaende_beeinflussen_nur_gueltige_dauer():
    """Fehlende Werte und unzulässige Zeitabstände werden nicht mitgezählt."""
    index = pd.DatetimeIndex(
        ["2026-01-01T00:00Z", "2026-01-01T00:01Z", "2026-01-01T00:03Z", "2026-01-01T00:04Z"]
    )
    df = pd.DataFrame({"raum_wohnzimmer_c": [18.0, 18.0, float("nan"), 20.0]}, index=index)
    cfg = Config(raum_soll_c={"wohnzimmer": 20.0})

    erg = analysiere_komfort(df, cfg)

    assert erg.anteil_unter_soll == {"wohnzimmer": 1.0}
    assert erg.bewertung == Bewertung.OK


def test_kein_raumtemperaturfeld_liefert_leeres_ergebnis():
    """Ohne Raumspalten gibt die Analyse ein neutrales Ergebnis zurück."""
    erg = analysiere_komfort(pd.DataFrame(index=pd.date_range(
        "2026-01-01", periods=1, tz="UTC"
    )), Config())

    assert erg.anteil_unter_soll == {}
    assert erg.kaeltester_raum is None
    assert erg.kaelteste_mitteltemperatur_c is None
    assert erg.bewertung == Bewertung.OK


def test_simulierte_raumtemperaturen_bleiben_ohne_fehlalarm():
    """Simulierte Normaltemperaturen erzeugen keine Komfortbefunde."""
    erg = analysiere_komfort(simuliere(tage=1), Config())

    assert set(erg.anteil_unter_soll) == {"wohnzimmer", "schlafzimmer"}
    assert erg.bewertung == Bewertung.OK
    assert erg.befunde == []
