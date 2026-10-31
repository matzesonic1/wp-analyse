"""Liest Messdaten aus einer CSV-Datei (z. B. Export aus Home Assistant oder Hersteller-Portal)."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from .base import DatenAdapter


class CsvAdapter(DatenAdapter):
    def __init__(self, pfad: str | Path, zeitspalte: str = "zeit", spalten_mapping: dict[str, str] | None = None):
        """spalten_mapping: Name in der CSV -> Projektname, z. B. {"Vorlauf": "vorlauf_c"}."""
        self.pfad = Path(pfad)
        self.zeitspalte = zeitspalte
        self.spalten_mapping = spalten_mapping or {}

    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        df = pd.read_csv(self.pfad)
        df = df.rename(columns=self.spalten_mapping)
        df.index = pd.to_datetime(df.pop(self.zeitspalte), utc=True)
        df = df.sort_index()
        return df[(df.index >= pd.Timestamp(von, tz="UTC")) & (df.index < pd.Timestamp(bis, tz="UTC"))]
