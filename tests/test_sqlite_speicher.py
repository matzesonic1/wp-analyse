"""Tests für Persistenz, Aktualisierung und Zeitraumabfragen des SQLite-Speichers."""

import json
import sqlite3
from datetime import UTC, datetime

import pandas as pd

from wpanalyse.models import Stoerung, WartungReparatur
from wpanalyse.speicher import SQLiteSpeicher


def test_speichert_und_laesst_zeitraum_mit_utc_index(tmp_path):
    """Messwerte bleiben nach erneutem Öffnen samt UTC-Index und fehlenden Werten erhalten."""
    pfad = tmp_path / "messwerte.sqlite"
    zeit = pd.date_range("2026-01-01", periods=3, freq="min", tz="UTC")
    df = pd.DataFrame(
        {"vorlauf_c": [32.5, None, 34.0], "verdichter_an": [True, False, True]},
        index=zeit,
    )

    with SQLiteSpeicher(pfad) as speicher:
        speicher.speichern(df)
    with SQLiteSpeicher(pfad) as speicher:
        ergebnis = speicher.lese(
            datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
        )

    assert ergebnis.index.equals(zeit[1:3])
    assert ergebnis.index.tz == UTC
    assert ergebnis["vorlauf_c"].iloc[0] != ergebnis["vorlauf_c"].iloc[0]
    assert ergebnis["verdichter_an"].tolist() == [False, True]


def test_speichern_aktualisiert_doppelten_zeitstempel(tmp_path):
    """Ein erneut gespeicherter Zeitstempel ersetzt den vorhandenen Datensatz."""
    with SQLiteSpeicher(tmp_path / "messwerte.sqlite") as speicher:
        zeit = pd.date_range("2026-01-01", periods=1, tz="UTC")
        speicher.speichern(pd.DataFrame({"vorlauf_c": [30.0]}, index=zeit))
        speicher.speichern(pd.DataFrame({"vorlauf_c": [31.0]}, index=zeit))

        ergebnis = speicher.lese(zeit[0], zeit[0] + pd.Timedelta(minutes=1))

    assert ergebnis["vorlauf_c"].tolist() == [31.0]


def test_laden_leerer_zeitraum_bewahrt_spalten_und_utc_index(tmp_path):
    """Auch ein leerer Lesezeitraum behält bekannte Spalten und UTC-Zeitzone."""
    with SQLiteSpeicher(tmp_path / "messwerte.sqlite") as speicher:
        speicher.speichern(pd.DataFrame(columns=["vorlauf_c"], index=pd.DatetimeIndex([], tz="UTC")))

        ergebnis = speicher.lese(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )

    assert ergebnis.empty
    assert list(ergebnis.columns) == ["vorlauf_c"]
    assert ergebnis.index.tz == UTC


def test_migriert_json_zeilen_und_spalten_transaktional_nach_standard(tmp_path):
    """Alte JSON-Messungen und ihre Spaltennamen bleiben nach Schemawechsel erhalten."""
    pfad = tmp_path / "alt.sqlite"
    zeit_ns = pd.Timestamp("2026-03-01T12:00:00Z").value
    with sqlite3.connect(pfad) as verbindung:
        verbindung.execute("CREATE TABLE messwerte (zeit_ns INTEGER PRIMARY KEY, daten TEXT NOT NULL)")
        verbindung.execute(
            "CREATE TABLE metadaten (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL)"
        )
        verbindung.execute(
            "INSERT INTO messwerte VALUES (?, ?)",
            (zeit_ns, json.dumps({"vorlauf_c": 34.5, "unbekannt": "unverändert"})),
        )
        verbindung.execute(
            "INSERT INTO metadaten VALUES ('spalten', ?)", (json.dumps(["vorlauf_c", "unbekannt"]),)
        )

    with SQLiteSpeicher(pfad, anlage_id="andere") as speicher:
        assert speicher.lese(
            datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 3, 2, tzinfo=UTC)
        ).empty
    with SQLiteSpeicher(pfad) as speicher:
        ergebnis = speicher.lese(
            datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 3, 2, tzinfo=UTC)
        )
        assert ergebnis.iloc[0].to_dict() == {
            "vorlauf_c": 34.5,
            "unbekannt": "unverändert",
        }
        assert speicher._verbindung.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'messwerte'"
        ).fetchone() is None


def test_gleicher_zeitpunkt_ist_pro_anlage_unabhaengig(tmp_path):
    """Mehrere Anlagen können denselben UTC-Zeitpunkt mit unterschiedlichen Werten besitzen."""
    pfad = tmp_path / "mehrere.sqlite"
    zeit = pd.date_range("2026-04-01", periods=1, tz="UTC")
    for anlage, temperatur in (("haus-a", 30.0), ("haus-b", 40.0)):
        with SQLiteSpeicher(pfad, anlage_id=anlage) as speicher:
            speicher.speichern(pd.DataFrame({"vorlauf_c": [temperatur]}, index=zeit))

    with SQLiteSpeicher(pfad, anlage_id="haus-a") as speicher_a:
        assert speicher_a.lese(zeit[0], zeit[0] + pd.Timedelta(minutes=1))["vorlauf_c"].tolist() == [30]
    with SQLiteSpeicher(pfad, anlage_id="haus-b") as speicher_b:
        assert speicher_b.lese(zeit[0], zeit[0] + pd.Timedelta(minutes=1))["vorlauf_c"].tolist() == [40]


def test_typisierte_felder_und_unbekannte_quellfelder(tmp_path):
    """Bekannte Felder sind typisiert und nicht zugeordnete Felder bleiben roh erhalten."""
    zeit = pd.date_range("2026-05-01", periods=1, tz="UTC")
    with SQLiteSpeicher(tmp_path / "felder.sqlite") as speicher:
        speicher.speichern(
            pd.DataFrame(
                {"verdichter_an": [True], "verdichter_hz": [42.5], "error_nr0": ["E17"]},
                index=zeit,
            )
        )
        ergebnis = speicher.lese(zeit[0], zeit[0] + pd.Timedelta(minutes=1))
        datenbankwerte = speicher._verbindung.execute(
            "SELECT verdichter_an, verdichter_hz, rohfelder_json FROM messwert"
        ).fetchone()

    assert ergebnis.iloc[0].to_dict() == {
        "verdichter_an": True,
        "verdichter_hz": 42.5,
        "error_nr0": "E17",
    }
    assert datenbankwerte == (1, 42.5, '{"error_nr0": "E17"}')


def test_raumwerte_werden_relational_und_kompatibel_gelesen(tmp_path):
    """Raumtemperaturen und optionale Sollwerte sind relational lesbar."""
    zeit = pd.date_range("2026-06-01", periods=2, freq="min", tz="UTC")
    with SQLiteSpeicher(tmp_path / "raeume.sqlite") as speicher:
        speicher.speichern(
            pd.DataFrame({"raum_wohnzimmer_c": [20.0, None], "vorlauf_c": [30, 31]}, index=zeit),
            raum_soll_c={"wohnzimmer": 21.0},
        )

        kompatibel = speicher.lese(zeit[0], zeit[1] + pd.Timedelta(minutes=1))
        raumwerte = speicher.lese_raum_messwerte(zeit[0], zeit[1] + pd.Timedelta(minutes=1))

    assert kompatibel["raum_wohnzimmer_c"].iloc[0] == 20.0
    assert pd.isna(kompatibel["raum_wohnzimmer_c"].iloc[1])
    assert raumwerte["raum_name"].tolist() == ["wohnzimmer", "wohnzimmer"]
    assert raumwerte["soll_c"].tolist() == [21.0, 21.0]
    assert pd.isna(raumwerte["raum_c"].iloc[1])


def test_stoerung_und_wartung_werden_ohne_diagnose_round_trip_gespeichert(tmp_path):
    """Rohcode und bestätigte Wartungsdaten bleiben unverändert und im Zeitraum filterbar."""
    start = datetime(2026, 7, 1, tzinfo=UTC)
    stoerung = Stoerung("stoerung-1", start, start.replace(hour=1), "E123", "Rohtext", "api")
    wartung = WartungReparatur("wartung-1", start, "Filter gereinigt", "Filter", "Verschmutzung", "service")
    with SQLiteSpeicher(tmp_path / "ereignisse.sqlite") as speicher:
        speicher.speichern_stoerung(stoerung)
        speicher.speichern_wartung_reparatur(wartung)

        assert speicher.lese_stoerungen(start, start.replace(hour=2)) == [stoerung]
        assert speicher.lese_wartung_reparaturen(start, start.replace(hour=2)) == [wartung]
        assert speicher.lese_stoerungen(start.replace(hour=1), start.replace(hour=2)) == []
