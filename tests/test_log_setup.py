"""Tests für die zentrale Logging-Konfiguration."""

import logging

from wpanalyse.log_setup import konfiguriere_logging


def test_log_stufe_standard_und_umgebungsvariable(monkeypatch, caplog):
    """INFO gilt standardmäßig; die Umgebungsvariable aktiviert Debug."""
    monkeypatch.delenv("WPANALYSE_LOG_LEVEL", raising=False)
    konfiguriere_logging()
    assert logging.getLogger().level == logging.INFO

    monkeypatch.setenv("WPANALYSE_LOG_LEVEL", "DEBUG")
    konfiguriere_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_explizite_log_stufe_hat_vorrang(monkeypatch):
    """Eine direkt übergebene Stufe überschreibt die Umgebungsvariable."""
    monkeypatch.setenv("WPANALYSE_LOG_LEVEL", "INFO")

    konfiguriere_logging("DEBUG")

    assert logging.getLogger().level == logging.DEBUG


def test_log_filter_redigiert_token_und_entfernt_traceback(caplog, monkeypatch):
    """Sensible Inhalte aus Service-Logs gelangen nicht in die Ausgabe."""
    token = "test-token-geheim"
    monkeypatch.setenv("HA_TOKEN", token)
    konfiguriere_logging()

    try:
        raise RuntimeError(f"Fehler mit {token}")
    except RuntimeError:
        with caplog.at_level(logging.ERROR, logger="wpanalyse.ha_monitor"):
            logging.getLogger("wpanalyse.ha_monitor").exception("Abfrage fehlgeschlagen: %s", token)

    assert token not in caplog.text
    assert "[GEHEIM]" in caplog.text
    assert "Traceback" not in caplog.text
    assert caplog.records[-1].exc_info is None
