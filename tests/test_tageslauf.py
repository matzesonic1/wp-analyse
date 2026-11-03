"""Tests für die Erzeugung von Tagesberichten aus dem SQLite-Speicher."""

import sqlite3
from datetime import date

import pandas as pd
import pytest

from wpanalyse.config import Config
from wpanalyse.speicher import SQLiteSpeicher
from wpanalyse.tageslauf import erzeuge_tagesbericht


def test_erzeugt_tagesbericht_aus_utc_zeitraum(tmp_path):
    """Der Bericht umfasst genau den gewählten UTC-Kalendertag."""
    speicher_pfad = tmp_path / "messwerte.sqlite"
    ziel = tmp_path / "bericht.md"
    index = pd.to_datetime(
        [
            "2026-01-09 23:59",
            "2026-01-10 00:00",
            "2026-01-10 23:59",
            "2026-01-11 00:00",
        ],
        utc=True,
    )
    df = pd.DataFrame(
        {
            "verdichter_an": [True, True, True, True],
            "vorlauf_c": [60.0, 35.0, 35.0, 60.0],
            "ruecklauf_c": [10.0, 30.0, 30.0, 10.0],
        },
        index=index,
    )

    with SQLiteSpeicher(speicher_pfad) as speicher:
        speicher.speichern(df)
        verwendeter_pfad = erzeuge_tagesbericht(
            speicher, Config(), date(2026, 1, 10), ziel
        )

    bericht = ziel.read_text(encoding="utf-8")
    assert verwendeter_pfad == ziel
    assert "# Tagesbericht – 2026-01-10" in bericht
    assert "**Mittlere Spreizung im Verdichterbetrieb:** 5.0 K" in bericht
    assert "Für diesen Tag liegen keine Messwerte vor." not in bericht


def test_erzeugt_lesbaren_leerbericht_fuer_tag_ohne_messwerte(tmp_path):
    """Ein leerer Tag wird mit dem vorhandenen verständlichen Hinweis berichtet."""
    ziel = tmp_path / "bericht.md"
    with SQLiteSpeicher(tmp_path / "messwerte.sqlite") as speicher:
        speicher.speichern(
            pd.DataFrame(
                {"verdichter_an": [True]},
                index=pd.DatetimeIndex(["2026-01-09 12:00"], tz="UTC"),
            )
        )

        verwendeter_pfad = erzeuge_tagesbericht(
            speicher, Config(), date(2026, 1, 10), ziel
        )

    bericht = ziel.read_text(encoding="utf-8")
    assert verwendeter_pfad == ziel
    assert "# Tagesbericht – 2026-01-10" in bericht
    assert "Für diesen Tag liegen keine Messwerte vor." in bericht


def test_speicherfehler_werden_nicht_verschluckt(tmp_path):
    """Fehler beim Lesen aus SQLite werden an den Aufrufer weitergegeben."""
    speicher = SQLiteSpeicher(tmp_path / "messwerte.sqlite")
    speicher.close()

    with pytest.raises(sqlite3.ProgrammingError):
        erzeuge_tagesbericht(
            speicher, Config(), date(2026, 1, 10), tmp_path / "bericht.md"
        )


def test_dateifehler_werden_nicht_verschluckt(tmp_path):
    """Fehler beim Schreiben des Berichts werden an den Aufrufer weitergegeben."""
    with SQLiteSpeicher(tmp_path / "messwerte.sqlite") as speicher, pytest.raises(FileNotFoundError):
        erzeuge_tagesbericht(
            speicher,
            Config(),
            date(2026, 1, 10),
            tmp_path / "nicht-vorhandener-ordner" / "bericht.md",
        )
