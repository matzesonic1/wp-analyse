"""Gemeinsame und sichere Logkonfiguration für die Kommandozeilenprogramme."""

import logging
import os
import re
import sys
import threading

_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_DASHBOARD_LOGSTUFEN = ("DEBUG", "INFO", "WARNING", "ERROR")
_DASHBOARD_LOGGING_SPERRE = threading.RLock()
_DASHBOARD_LOGGING_AKTIV = True
_DASHBOARD_LOGGING_STUFE: str | None = None
_GEHEIMNIS_NAME = re.compile(
    r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API[_-]?KEY|AUTH|TOPIC",
    re.IGNORECASE,
)


class _GeheimnisFilter(logging.Filter):
    """Redigiert bekannte Zugangsdaten und unterdrückt Tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Bereinigt die Meldung vor der Ausgabe."""
        try:
            nachricht = record.getMessage()
        except Exception:  # noqa: BLE001 - Fehlformatierte Logdaten duerfen nicht herausfallen.
            nachricht = "Logmeldung konnte nicht formatiert werden"

        if record.exc_info:
            nachricht = "Fehlerdetails ausgeblendet"
            record.exc_info = None
        record.exc_text = None
        record.stack_info = None

        geheimnisse = sorted(
            (
                wert
                for name, wert in os.environ.items()
                if wert and _GEHEIMNIS_NAME.search(name)
            ),
            key=len,
            reverse=True,
        )
        for geheimnis in geheimnisse:
            nachricht = nachricht.replace(geheimnis, "[GEHEIM]")

        record.msg = nachricht
        record.args = ()
        return True


_geheimnis_filter = _GeheimnisFilter()


def konfiguriere_logging(stufe: str | None = None, *, logger_name: str | None = None) -> None:
    """Konfiguriert Logs; optional nur für einen Logger-Namensraum."""
    name = (stufe if stufe is not None else os.environ.get("WPANALYSE_LOG_LEVEL", "INFO")).upper()
    level = logging.getLevelName(name)
    if not isinstance(level, int):
        raise ValueError("Unbekannte Logstufe")  # noqa: TRY004 - Der Logstufenwert ist ungültig.

    ziel = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    ziel.setLevel(level)
    if logger_name:
        ziel.propagate = False
    for handler in ziel.handlers:
        if _geheimnis_filter not in handler.filters:
            handler.addFilter(_geheimnis_filter)
    handler = next(
        (handler for handler in ziel.handlers if getattr(handler, "_wpanalyse_handler", False)),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler._wpanalyse_handler = True
        ziel.addHandler(handler)
    else:
        handler.setStream(sys.stdout)
    if _geheimnis_filter not in handler.filters:
        handler.addFilter(_geheimnis_filter)
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.setLevel(level)


def dashboard_logging_einstellungen() -> tuple[bool, str]:
    """Liefert die prozessweiten Dashboard-Logging-Einstellungen."""
    global _DASHBOARD_LOGGING_STUFE
    with _DASHBOARD_LOGGING_SPERRE:
        if _DASHBOARD_LOGGING_STUFE is None:
            stufe = os.environ.get("WPANALYSE_LOG_LEVEL", "INFO").upper()
            _DASHBOARD_LOGGING_STUFE = stufe if stufe in _DASHBOARD_LOGSTUFEN else "INFO"
        _konfiguriere_dashboard_logging()
        return _DASHBOARD_LOGGING_AKTIV, _DASHBOARD_LOGGING_STUFE


def setze_dashboard_logging(*, aktiviert: bool | None = None, stufe: str | None = None) -> None:
    """Ändert die prozessweiten Dashboard-Logging-Einstellungen."""
    global _DASHBOARD_LOGGING_AKTIV, _DASHBOARD_LOGGING_STUFE
    with _DASHBOARD_LOGGING_SPERRE:
        if _DASHBOARD_LOGGING_STUFE is None:
            dashboard_logging_einstellungen()
        if aktiviert is not None:
            _DASHBOARD_LOGGING_AKTIV = aktiviert
        if stufe is not None:
            stufe = stufe.upper()
            if stufe not in _DASHBOARD_LOGSTUFEN:
                raise ValueError("Unbekannte Logstufe")
            _DASHBOARD_LOGGING_STUFE = stufe
        _konfiguriere_dashboard_logging()


def _konfiguriere_dashboard_logging() -> None:
    stufe = _DASHBOARD_LOGGING_STUFE if _DASHBOARD_LOGGING_AKTIV else "ERROR"
    konfiguriere_logging(stufe, logger_name="wpanalyse")
