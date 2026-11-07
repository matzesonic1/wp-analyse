"""Tests für die Übergabe der Supervisor-App-Konfiguration."""

import importlib.util
from pathlib import Path

import pytest

_PFAD = Path(__file__).parents[1] / "wp-analyse" / "run.py"
_SPEZ = importlib.util.spec_from_file_location("ha_app_run", _PFAD)
assert _SPEZ is not None and _SPEZ.loader is not None
ha_app_run = importlib.util.module_from_spec(_SPEZ)
_SPEZ.loader.exec_module(ha_app_run)


@pytest.mark.parametrize(
    ("optionen", "logstufe"),
    [
        ({"log_level": "DEBUG"}, "DEBUG"),
        ({}, "INFO"),
    ],
)
def test_supervisor_uebergibt_logstufe(monkeypatch, optionen, logstufe):
    """Supervisor-Optionen setzen die Umgebungsstufe mit INFO-Standard."""
    aufrufe = {}
    monkeypatch.setattr(ha_app_run, "_optionen_laden", lambda: optionen)

    def main_spion(argv):
        aufrufe["argv"] = argv
        aufrufe["logstufe"] = ha_app_run.os.environ["WPANALYSE_LOG_LEVEL"]
        return 0

    monkeypatch.setattr(ha_app_run, "main", main_spion)

    assert ha_app_run.main_app() == 0
    assert aufrufe["logstufe"] == logstufe
    assert aufrufe["argv"] == ["--db", "/data/wp.sqlite", "--intervall", "60"]
