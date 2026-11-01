"""Orchestriert das Sammeln und Speichern von Wärmepumpen-Messwerten."""

from datetime import datetime

import pandas as pd

from wpanalyse.adapters.base import DatenAdapter
from wpanalyse.speicher.sqlite import SQLiteSpeicher


def sammle_und_speichere(
    adapter: DatenAdapter,
    speicher: SQLiteSpeicher,
    von: datetime,
    bis: datetime,
) -> pd.DataFrame:
    """Sammelt Messwerte für einen Zeitraum, speichert sie und gibt sie zurück."""
    messwerte = adapter.lese(von, bis)
    speicher.speichern(messwerte)
    return messwerte
