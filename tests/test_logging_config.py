"""Tests für die zentrale Logkonfiguration."""

import logging
import sys

import pytest

from wpanalyse import logging_config
from wpanalyse.logging_config import konfiguriere_logging


@pytest.fixture(autouse=True)
def _logstufe_zuruecksetzen():
    root = logging.getLogger()
    stufe = root.level
    yield
    root.setLevel(stufe)


@pytest.fixture
def _dashboard_logger_zuruecksetzen(monkeypatch):
    logger = logging.getLogger("wpanalyse")
    stufe = logger.level
    weiterreichen = logger.propagate
    handler = list(logger.handlers)
    handler_stufen = {eintrag: eintrag.level for eintrag in handler}
    monkeypatch.setattr(logging_config, "_DASHBOARD_LOGGING_AKTIV", True)
    monkeypatch.setattr(logging_config, "_DASHBOARD_LOGGING_STUFE", "INFO")
    yield
    for eintrag in list(logger.handlers):
        if eintrag not in handler:
            logger.removeHandler(eintrag)
            eintrag.close()
    logger.setLevel(stufe)
    logger.propagate = weiterreichen
    for eintrag, handler_stufe in handler_stufen.items():
        eintrag.setLevel(handler_stufe)


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


def test_dashboard_logstufe_kommt_initial_aus_der_umgebung(monkeypatch, _dashboard_logger_zuruecksetzen):
    """Die Prozesskonfiguration initialisiert die Sidebar-Auswahl aus der Umgebungsvariable."""
    monkeypatch.setattr(logging_config, "_DASHBOARD_LOGGING_STUFE", None)
    monkeypatch.setenv("WPANALYSE_LOG_LEVEL", "WARNING")

    assert logging_config.dashboard_logging_einstellungen() == (True, "WARNING")
    assert logging.getLogger("wpanalyse").level == logging.WARNING


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


def test_dashboard_logging_ist_prozessweit_und_belaesst_root_und_streamlit_unveraendert(
    _dashboard_logger_zuruecksetzen, capsys
):
    """Dashboard-Logs bleiben separat; ausgeschaltet werden nur Meldungen unter ERROR gefiltert."""
    root = logging.getLogger()
    root_stufe = root.level
    streamlit_logger = logging.getLogger("streamlit.test")
    streamlit_stufe = streamlit_logger.level

    logging_config.setze_dashboard_logging(aktiviert=False, stufe="DEBUG")
    assert logging_config.dashboard_logging_einstellungen() == (False, "DEBUG")
    assert logging.getLogger("wpanalyse").level == logging.ERROR
    assert root.level == root_stufe
    assert streamlit_logger.level == streamlit_stufe
    logger = logging.getLogger("wpanalyse.dashboard_test")
    logger.warning("Hinweis ausgeblendet")
    logger.error("Fehler bleibt sichtbar")
    ausgabe = capsys.readouterr().out
    assert "Hinweis ausgeblendet" not in ausgabe
    assert "Fehler bleibt sichtbar" in ausgabe

    logging_config.setze_dashboard_logging(aktiviert=True)
    assert logging.getLogger("wpanalyse").level == logging.DEBUG
