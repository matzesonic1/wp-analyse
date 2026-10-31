"""Schnittstelle für alle Datenquellen."""

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class DatenAdapter(ABC):
    """Liest Messdaten aus einer Quelle und liefert einen DataFrame im Projektformat.

    Format: DatetimeIndex (UTC), Spalten wie in docs/fachwissen.md, Raumtemperaturen als 'raum_<name>_c'.
    """

    @abstractmethod
    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        """Liefert alle Messwerte im Zeitraum [von, bis)."""

    def aktuell(self) -> pd.DataFrame:
        """Liefert den neuesten Messwert. Adapter mit Live-Zugriff sollten das überschreiben."""
        raise NotImplementedError
