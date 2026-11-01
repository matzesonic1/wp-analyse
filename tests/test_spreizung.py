"""Tests für Spreizungskennzahlen und die Erkennung eines langfristigen Anstiegs."""

import pandas as pd

from wpanalyse.analyse.spreizung import analysiere_spreizung
from wpanalyse.config import Config
from wpanalyse.models import Bewertung
from wpanalyse.simulation import simuliere


def test_normalbetrieb_ohne_fehlalarm_und_mittel_nur_bei_laufendem_verdichter():
    """Im Normalbetrieb wird nur die Spreizung während des Verdichterlaufs gemittelt."""
    erg = analysiere_spreizung(simuliere(tage=3, takten=False), Config())

    assert erg.bewertung == Bewertung.OK
    assert erg.befunde == []
    assert 4.5 <= erg.mittlere_spreizung_k <= 5.5


def test_verschmutzter_filter_wird_nach_anstieg_erkannt():
    """Ein Anstieg des 7-Tage-Mittels löst den Hinweis nach A3 aus."""
    index = pd.date_range("2026-01-01", periods=31, freq="D", tz="UTC")
    spreizung = [5.0] * 24 + [8.0] * 7
    df = pd.DataFrame(
        {
            "vorlauf_c": [35.0] * len(index),
            "ruecklauf_c": [35.0 - wert for wert in spreizung],
            "verdichter_an": [True] * len(index),
        },
        index=index,
    )

    erg = analysiere_spreizung(df, Config())

    assert erg.bewertung == Bewertung.HINWEIS
    assert erg.befunde[0].regel_id == "A3"
    assert "Filter" in erg.befunde[0].text
