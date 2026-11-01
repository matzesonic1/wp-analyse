"""Tests für die Orchestrierung von Sammellauf und Speicherung."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from wpanalyse.adapters.base import DatenAdapter
from wpanalyse.erfassung import sammle_und_speichere
from wpanalyse.speicher import SQLiteSpeicher


class FakeAdapter(DatenAdapter):
    def __init__(self, messwerte: pd.DataFrame):
        self.messwerte = messwerte
        self.zeitraum = None

    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        self.zeitraum = (von, bis)
        return self.messwerte


def test_sammelt_speichert_und_gibt_messwerte_zurueck():
    von = datetime(2026, 1, 1, tzinfo=UTC)
    bis = datetime(2026, 1, 1, 2, tzinfo=UTC)
    messwerte = pd.DataFrame(
        {"vorlauf_c": [32.5, 33.0], "verdichter_an": [True, False]},
        index=pd.date_range(von, periods=2, freq="h").as_unit("ns"),
    )
    adapter = FakeAdapter(messwerte)

    with SQLiteSpeicher(":memory:") as speicher:
        ergebnis = sammle_und_speichere(adapter, speicher, von, bis)
        gespeichert = speicher.lese(von, bis)

    assert adapter.zeitraum == (von, bis)
    assert ergebnis is messwerte
    pd.testing.assert_frame_equal(gespeichert, messwerte, check_freq=False)


def test_adapterfehler_werden_weitergereicht():
    class FehlerAdapter(DatenAdapter):
        def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
            raise RuntimeError("Adapterfehler")

    with SQLiteSpeicher(":memory:") as speicher, pytest.raises(
        RuntimeError, match="Adapterfehler"
    ):
        sammle_und_speichere(
            FehlerAdapter(),
            speicher,
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )


def test_speicherfehler_werden_weitergereicht():
    class FehlerSpeicher:
        def speichern(self, messwerte: pd.DataFrame) -> None:
            raise RuntimeError("Speicherfehler")

    adapter = FakeAdapter(pd.DataFrame(index=pd.DatetimeIndex([], tz=UTC)))
    von = datetime(2026, 1, 1, tzinfo=UTC)
    bis = datetime(2026, 1, 2, tzinfo=UTC)

    with pytest.raises(RuntimeError, match="Speicherfehler"):
        sammle_und_speichere(adapter, FehlerSpeicher(), von, bis)

    assert adapter.zeitraum == (von, bis)
