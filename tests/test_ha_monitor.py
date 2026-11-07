"""Tests für CLI, Speicherung und geordnetes Stoppen des HA-Monitors."""

import logging
import signal
from datetime import UTC, datetime

import pandas as pd

from wpanalyse import ha_monitor
from wpanalyse.speicher.sqlite import SQLiteSpeicher


class _FakeAdapter:
    """Liefert eine feste synthetische Messung oder einen Testfehler."""

    def __init__(self, fehler: Exception | None = None):
        self.fehler = fehler

    def aktuell(self) -> pd.DataFrame:
        if self.fehler:
            raise self.fehler
        return pd.DataFrame(
            {"aussen_c": [4.5], "verdichter_an": [True]},
            index=pd.DatetimeIndex([datetime(2026, 1, 2, tzinfo=UTC)]),
        )


def _env(monkeypatch, token: str = "test-token") -> None:
    monkeypatch.setenv("HA_URL", "http://ha.test:8123")
    monkeypatch.setenv("HA_TOKEN", token)
    monkeypatch.setenv("NOVELAN_ENTITY_AUSSEN_C", "sensor.aussen")


def test_main_speichert_einmalige_messung_in_sqlite(tmp_path, monkeypatch):
    """Der CLI-Einmalmodus schreibt Adapterwerte in den angegebenen Speicher."""
    _env(monkeypatch)
    monkeypatch.setattr(ha_monitor, "NovelanLadv9Adapter", _FakeAdapter)
    db_pfad = tmp_path / "messwerte.sqlite"

    ergebnis = ha_monitor.main(["--db", str(db_pfad), "--intervall", "75", "--einmal"])

    assert ergebnis == 0
    with SQLiteSpeicher(db_pfad) as speicher:
        messwerte = speicher.lese(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC))
    assert messwerte.loc["2026-01-02T00:00:00Z", "aussen_c"] == 4.5
    assert messwerte.loc["2026-01-02T00:00:00Z", "verdichter_an"]


def test_main_begrenzt_pollingintervall_auf_minimum(tmp_path, monkeypatch):
    """Ein zu kleines CLI-Intervall wird auf den Regler-schonenden Mindestwert gesetzt."""
    _env(monkeypatch)
    erfasste_intervalle = {}

    class _MonitorSpy:
        def __init__(self, _adapter, _speicher, intervall_s, min_intervall_s):
            erfasste_intervalle["wert"] = intervall_s
            erfasste_intervalle["minimum"] = min_intervall_s

        def einmal(self):
            return True

    monkeypatch.setattr(ha_monitor, "NovelanLadv9Adapter", _FakeAdapter)
    monkeypatch.setattr(ha_monitor, "Monitor", _MonitorSpy)

    ergebnis = ha_monitor.main(
        ["--db", str(tmp_path / "messwerte.sqlite"), "--intervall", "20", "--einmal"]
    )

    assert ergebnis == 0
    assert erfasste_intervalle == {"wert": 20.0, "minimum": 60.0}


def test_main_redigiert_token_und_fehlermeldung(caplog, monkeypatch, tmp_path):
    """Netzwerkfehler bleiben sichtbar, geben aber weder Token noch Traceback aus."""
    token = "nicht-fuer-logs"
    _env(monkeypatch, token)
    monkeypatch.setattr(
        ha_monitor,
        "NovelanLadv9Adapter",
        lambda: _FakeAdapter(RuntimeError(f"Fehler mit {token}")),
    )

    with caplog.at_level(logging.ERROR):
        ergebnis = ha_monitor.main(["--db", str(tmp_path / "messwerte.sqlite"), "--einmal"])

    assert ergebnis == 1
    assert "Abfrage fehlgeschlagen" in caplog.text
    assert token not in caplog.text
    assert "Traceback" not in caplog.text


def test_main_beendet_lauf_bei_sigterm_und_stellt_handler_wieder_her(
    monkeypatch, tmp_path
):
    """SIGTERM setzt das Stop-Ereignis und die bisherigen Handler werden restauriert."""
    _env(monkeypatch)
    monkeypatch.setattr(ha_monitor, "NovelanLadv9Adapter", _FakeAdapter)
    registrierte_handler = {}
    wiederhergestellte = []
    vorheriger_handler = object()

    def signal_mock(signal_nummer, handler):
        if handler is not vorheriger_handler:
            registrierte_handler[signal_nummer] = handler
            if signal_nummer == signal.SIGTERM:
                handler(signal_nummer, None)
            return vorheriger_handler
        wiederhergestellte.append(signal_nummer)
        return None

    class _FakeMonitor:
        def __init__(self, *_args, **_kwargs):
            pass

        def laufen(self, stop, schlafen):
            assert stop()
            assert schlafen(0)

    monkeypatch.setattr(ha_monitor, "Monitor", _FakeMonitor)
    monkeypatch.setattr(ha_monitor.signal, "signal", signal_mock)

    ergebnis = ha_monitor.main(["--db", str(tmp_path / "messwerte.sqlite")])

    assert ergebnis == 0
    assert set(registrierte_handler) == {signal.SIGINT, signal.SIGTERM}
    assert set(wiederhergestellte) == {signal.SIGINT, signal.SIGTERM}
