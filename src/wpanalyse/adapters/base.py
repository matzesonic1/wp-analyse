"""Abstrakter Vertrag für Datenquellen der Wärmepumpen-Anwendung."""

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class DatenAdapter(ABC):
    """Liest Messdaten aus einer Quelle und liefert einen DataFrame im Projektformat.

    Das Ergebnis verwendet einen UTC-DatetimeIndex sowie die Feldnamen aus
    ``docs/fachwissen.md``. Raumtemperaturen werden als ``raum_<name>_c``
    abgelegt.
    """

    @abstractmethod
    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        """Liefert Messwerte im halboffenen Zeitraum ``[von, bis)``."""

    def aktuell(self) -> pd.DataFrame:
        """Liefert aktuelle Messwerte, sofern die Datenquelle Live-Zugriff bietet.

        Adapter ohne Live-Zugriff unterstützen diese optionale Operation nicht.
        """
        raise NotImplementedError
