"""Tests der Verdichter-Bewertung mit synthetischen Zählerdaten."""

import pandas as pd

from wpanalyse.analyse.verdichter import bewerte_verdichter, starts_pro_stunde_max
from wpanalyse.config import VerdichterConfig

JETZT = pd.Timestamp("2026-11-03 21:00", tz="UTC")


def test_zaehler_mit_altwerten_wird_erkannt():
    ergebnis = bewerte_verdichter(9927, 31_216_686, JETZT, VerdichterConfig())

    assert ergebnis.zaehler_enthaelt_altwerte is True
    assert ergebnis.max_betriebszeit_seit_tausch_h < ergebnis.betriebszeit_h
    assert any("nicht zurückgesetzt" in h for h in ergebnis.hinweise)


def test_bekannte_basis_wird_abgezogen():
    cfg = VerdichterConfig(basis_starts=9000, basis_betriebszeit_s=31_000_000)

    ergebnis = bewerte_verdichter(9927, 31_216_686, JETZT, cfg)

    assert ergebnis.zaehler_enthaelt_altwerte is False
    assert ergebnis.starts == 927
    assert round(ergebnis.betriebszeit_h) == 60
    assert round(ergebnis.mittlere_laufzeit_min) == 4
    assert any("unter 10 min" in h for h in ergebnis.hinweise)


def test_gute_laufzeit_ohne_hinweis():
    cfg = VerdichterConfig(basis_starts=0, basis_betriebszeit_s=0)

    ergebnis = bewerte_verdichter(100, 100 * 60 * 60, JETZT, cfg)

    assert ergebnis.hinweise == []


def test_starts_pro_stunde_spitze():
    index = pd.date_range("2026-01-01 10:00", periods=8, freq="10min", tz="UTC")
    df = pd.DataFrame({"verdichter_starts_zaehler": [100, 101, 102, 103, 104, 105, 106, 107]}, index=index)

    assert starts_pro_stunde_max(df) == 6
    cfg = VerdichterConfig(basis_starts=0, basis_betriebszeit_s=0, max_starts_pro_stunde=4)
    ergebnis = bewerte_verdichter(107, 107 * 3600, JETZT, cfg, df)
    assert any("Starts innerhalb einer Stunde" in h for h in ergebnis.hinweise)


def test_ohne_zaehlerverlauf():
    assert starts_pro_stunde_max(pd.DataFrame()) is None
