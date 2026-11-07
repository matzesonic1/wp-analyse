"""Tests für die zentrale Logkonfiguration."""

import logging
import sys

import pytest

from wpanalyse.logging_config import konfiguriere_logging


@pytest.fixture(autouse=True)
def _logstufe_zuruecksetzen():
    root = logging.getLogger()
    stufe = root.level
    yield
    root.setLevel(stufe)


def test_standard_logstufe_ist_info(monkeypatch):
    """Ohne Vorgabe verwenden alle Einstiegspunkte INFO als Standard."""
    monkeypatch.delenv("WPANALYSE_LOG_LEVEL", raising=False)

    konfiguriere_logging()

    assert logging.getLogger().level == logging.INFO


def test_debug_logstufe_ist_per_umgebung_konfigurierbar(monkeypatch):
    """Die gemeinsame Umgebungsvariable aktiviert Debug für alle Programme."""
    monkeypatch.setenv("WPANALYSE_LOG_LEVEL", "debug")

    konfiguriere_logging()

    assert logging.getLogger().level == logging.DEBUG


def test_explizite_logstufe_ueberschreibt_umgebung(monkeypatch):
    """Ein expliziter Funktionsparameter hat Vorrang vor der Umgebungsvariable."""
    monkeypatch.setenv("WPANALYSE_LOG_LEVEL", "WARNING")

    konfiguriere_logging("DEBUG")

    assert logging.getLogger().level == logging.DEBUG


def test_logging_ist_idempotent_und_schreibt_nach_stdout():
    """Wiederholte Konfiguration verwendet einen stdout-Handler weiter."""
    konfiguriere_logging()
    handler = next(
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_wpanalyse_handler", False)
    )
    konfiguriere_logging("DEBUG")
    handler_nachher = next(
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_wpanalyse_handler", False)
    )

    assert handler_nachher is handler
    assert handler.stream is sys.stdout
    assert handler.level == logging.DEBUG
    assert handler.formatter._fmt == "%(asctime)s %(levelname)s %(message)s"


def test_ungueltige_logstufe_wird_abgelehnt(monkeypatch):
    """Ein Tippfehler in der Konfiguration wird nicht stillschweigend ignoriert."""
    monkeypatch.setenv("WPANALYSE_LOG_LEVEL", "unbekannt")

    with pytest.raises(ValueError, match="Unbekannte Logstufe"):
        konfiguriere_logging()


def test_geheimnisse_und_tracebacks_werden_redigiert(caplog, monkeypatch):
    """Auch direkte Tokens und Exception-Tracebacks erscheinen nicht im Log."""
    token = "test-token-geheim"
    api_schluessel = "test-api-schluessel"
    ntfy_token = "test-ntfy-token"
    monkeypatch.setenv("HA_TOKEN", token)
    monkeypatch.setenv("CUSTOM_API_KEY", api_schluessel)
    monkeypatch.setenv("NTFY_TOKEN", ntfy_token)
    konfiguriere_logging("DEBUG")
    logger = logging.getLogger("wpanalyse.logging_test")

    with caplog.at_level(logging.DEBUG):
        logger.error("Verbindung mit %s fehlgeschlagen", token)
        logger.error("Unbekannter Dienst: %s %s", api_schluessel, ntfy_token)
        try:
            raise RuntimeError(f"Fehler mit {token}")
        except RuntimeError:
            logger.exception("Adapterfehler")

    assert token not in caplog.text
    assert api_schluessel not in caplog.text
    assert ntfy_token not in caplog.text
    assert "[GEHEIM]" in caplog.text
    assert "Traceback" not in caplog.text
    assert "Fehlerdetails ausgeblendet" in caplog.text
