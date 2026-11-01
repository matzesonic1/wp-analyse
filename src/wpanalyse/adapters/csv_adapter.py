"""Liest und normalisiert Messdaten aus einer CSV-Datei."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from .base import DatenAdapter


class CsvAdapter(DatenAdapter):
    """Passt CSV-Spalten und Zeitstempel an das Projektformat an."""

    def __init__(self, pfad: str | Path, zeitspalte: str = "zeit", spalten_mapping: dict[str, str] | None = None):
        """Initialisiert den CSV-Adapter.

        Args:
            pfad: Pfad zur Quelldatei.
            zeitspalte: Name der CSV-Spalte mit den Messzeitpunkten.
            spalten_mapping: Zuordnung von CSV-Namen zu Projektfeldnamen.
        """
        self.pfad = Path(pfad)
        self.zeitspalte = zeitspalte
        self.spalten_mapping = spalten_mapping or {}

    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        """Liest die CSV und filtert auf den UTC-Zeitraum ``[von, bis)``."""
        df = pd.read_csv(self.pfad)
        df = df.rename(columns=self.spalten_mapping)
        df.index = pd.to_datetime(df.pop(self.zeitspalte), utc=True)
        df = df.sort_index()
        return df[(df.index >= pd.Timestamp(von, tz="UTC")) & (df.index < pd.Timestamp(bis, tz="UTC"))]
