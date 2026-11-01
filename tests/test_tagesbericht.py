"""Tests für Kennzahlen, Warnungen und fehlende Daten im Tagesbericht."""

import pandas as pd

from wpanalyse.bericht.tagesbericht import erstelle_tagesbericht
from wpanalyse.config import Config
from wpanalyse.simulation import simuliere


def test_tagesbericht_enthaelt_kennzahlen_raumkomfort_und_auffaelligkeiten():
    """Der Bericht enthält die verfügbaren Energie-, Taktungs- und Komfortangaben."""
    df = simuliere(tage=1)
    df["waerme_kwh"] = df["waerme_w"] / 60_000
    df["strom_kwh"] = df["leistung_w"] / 60_000
    df["raum_bad_c"] = 20.0

    bericht = erstelle_tagesbericht(df, Config())

    assert "# Tagesbericht – 2026-01-10" in bericht
    assert "**Arbeitszahl (AZ):**" in bericht
    assert "**Verdichterstarts:**" in bericht
    assert "**Verdichterlaufzeit:**" in bericht
    assert "**Mittlere Spreizung im Verdichterbetrieb:**" in bericht
    assert "**wohnzimmer:**" in bericht
    assert "**bad:**" in bericht
    assert "Auffälligkeiten" in bericht


def test_tagesbericht_meldet_fehlen_energiemesswerte_und_raumwarnung():
    """Fehlende Energiespalten und anhaltend niedrige Raumtemperatur werden benannt."""
    index = pd.date_range("2026-01-10", periods=181, freq="min", tz="UTC")
    df = pd.DataFrame(
        {
            "verdichter_an": [False] * len(index),
            "vorlauf_c": [35.0] * len(index),
            "ruecklauf_c": [30.0] * len(index),
            "raum_wohnzimmer_c": [18.0] * len(index),
        },
        index=index,
    )

    bericht = erstelle_tagesbericht(df, Config())

    assert "AZ):** nicht verfügbar" in bericht
    assert "waerme_kwh, strom_kwh" in bericht
    assert "A5 (warnung)" in bericht
    assert "A6 (kritisch)" not in bericht


def test_tagesbericht_meldet_taktung_und_kritisch_kalten_raum():
    """Der Bericht weist häufige Starts und eine kritische Raumtemperatur aus."""
    index = pd.date_range("2026-01-10", periods=24 * 60, freq="min", tz="UTC")
    minute = range(len(index))
    df = pd.DataFrame(
        {
            "verdichter_an": [wert % 12 < 6 for wert in minute],
            "vorlauf_c": [35.0] * len(index),
            "ruecklauf_c": [30.0] * len(index),
            "raum_wohnzimmer_c": [16.5] * len(index),
        },
        index=index,
    )

    bericht = erstelle_tagesbericht(df, Config(raum_soll_c={}))

    assert "A1 (warnung)" in bericht
    assert "wohnzimmer:** nicht bewertbar" in bericht
    assert "A6 (kritisch)" in bericht


def test_tagesbericht_meldet_taktung_im_hinweisbereich():
    """Taktung im Hinweisbereich wird als Hinweis und nicht als Warnung eingestuft."""
    index = pd.date_range("2026-01-10", periods=24 * 60, freq="min", tz="UTC")
    minute = range(len(index))
    df = pd.DataFrame(
        {
            "verdichter_an": [wert % 120 < 15 for wert in minute],
            "vorlauf_c": [35.0] * len(index),
            "ruecklauf_c": [30.0] * len(index),
        },
        index=index,
    )

    bericht = erstelle_tagesbericht(df, Config())

    assert "A1 (hinweis)" in bericht
    assert "11 Verdichterstarts" in bericht


def test_tagesbericht_zaehlt_grosse_datenluecken_nicht_als_tagesabdeckung():
    """Eine große Messlücke gilt nicht als ausreichende Tagesabdeckung."""
    index = pd.to_datetime(["2026-01-10 00:00", "2026-01-10 23:59"], utc=True)
    df = pd.DataFrame(
        {
            "verdichter_an": [False, True],
            "vorlauf_c": [35.0, 35.0],
            "ruecklauf_c": [30.0, 30.0],
        },
        index=index,
    )

    bericht = erstelle_tagesbericht(df, Config())

    assert "Verdichterstarts:** nicht verfügbar" in bericht
    assert "A1 (" not in bericht


def test_tagesbericht_zeigt_fehlenden_tag_und_keine_messwerte():
    """Ein angefragter Tag ohne Messwerte erhält einen verständlichen Hinweis."""
    index = pd.date_range("2026-01-10", periods=3, freq="h", tz="UTC")
    df = pd.DataFrame({"verdichter_an": [False, True, False]}, index=index)

    bericht = erstelle_tagesbericht(df, Config(), "2026-01-11")

    assert "# Tagesbericht – 2026-01-11" in bericht
    assert "Für diesen Tag liegen keine Messwerte vor." in bericht


def test_tagesbericht_waehlt_letzten_tag_bei_mehrtaegigen_daten():
    """Ohne Datumsauswahl wird der letzte im DataFrame enthaltene Tag verwendet."""
    df = simuliere(tage=2)

    bericht = erstelle_tagesbericht(df, Config())

    assert "# Tagesbericht – 2026-01-11" in bericht
