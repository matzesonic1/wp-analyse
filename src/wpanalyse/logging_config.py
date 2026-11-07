"""Gemeinsame und sichere Logkonfiguration für die Kommandozeilenprogramme."""

import logging
import os
import re
import sys
import threading
import time

_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_DEBUG_FORMAT = "%(asctime)s %(levelname)s pid=%(process)d quelle=%(name)s.%(funcName)s %(message)s"
_DASHBOARD_LOGSTUFEN = ("DEBUG", "INFO", "WARNING", "ERROR")
_DASHBOARD_LOGGING_SPERRE = threading.RLock()
_DASHBOARD_LOGGING_AKTIV = True
_DASHBOARD_LOGGING_STUFE: str | None = None
_DASHBOARD_INITIALISIERT = False
_DIAGNOSE_SPERRE = threading.RLock()
_DIAGNOSE_STATUS: dict[str, tuple[str, float, int]] = {}
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


class _DiagnoseFormatter(logging.Formatter):
    """Ergänzt Herkunftsinformationen ausschließlich bei DEBUG-Ereignissen."""

    def __init__(self) -> None:
        super().__init__(_FORMAT)
        self._debug_formatter = logging.Formatter(_DEBUG_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno == logging.DEBUG:
            return self._debug_formatter.format(record)
        return super().format(record)


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
    handler.setFormatter(_DiagnoseFormatter())
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


def initialisiere_dashboard_logging() -> None:
    """Initialisiert die Dashboard-Diagnose einmal pro Prozess."""
    global _DASHBOARD_INITIALISIERT
    with _DASHBOARD_LOGGING_SPERRE:
        dashboard_logging_einstellungen()
        if not _DASHBOARD_INITIALISIERT:
            _DASHBOARD_INITIALISIERT = True
            logging.getLogger("wpanalyse.dashboard").info("Dashboard initialisiert")


def diagnose_gedrosselt(
    logger: logging.Logger,
    stufe: int,
    ereignis: str,
    zustand: str,
    intervall: tuple[float, float] | None = None,
) -> None:
    """Protokolliert Zustandswechsel und fasst wiederholte Ereignisse zusammen."""
    if not logger.isEnabledFor(stufe):
        return
    jetzt = time.monotonic()
    with _DIAGNOSE_SPERRE:
        vorher = _DIAGNOSE_STATUS.get(ereignis)
        if vorher is None or vorher[0] != zustand:
            if vorher is not None and vorher[2]:
                logger.log(stufe, "%s zustand=%s wiederholungen=%d", ereignis, vorher[0], vorher[2], stacklevel=2)
            if intervall is None:
                logger.log(stufe, "%s zustand=%s", ereignis, zustand, stacklevel=2)
            else:
                logger.log(
                    stufe, "%s zustand=%s alter_s=%.0f grenze_s=%.0f",
                    ereignis, zustand, *intervall,
                    stacklevel=2,
                )
            _DIAGNOSE_STATUS[ereignis] = (zustand, jetzt, 0)
        elif jetzt - vorher[1] >= 60:
            logger.log(stufe, "%s zustand=%s wiederholungen=%d", ereignis, zustand, vorher[2] + 1, stacklevel=2)
            _DIAGNOSE_STATUS[ereignis] = (zustand, jetzt, 0)
        else:
            _DIAGNOSE_STATUS[ereignis] = (zustand, vorher[1], vorher[2] + 1)


def diagnose_wiederhergestellt(logger: logging.Logger, stufe: int, ereignis: str) -> None:
    """Schließt eine Fehlerfolge ab und meldet gegebenenfalls unterdrückte Ereignisse."""
    with _DIAGNOSE_SPERRE:
        vorher = _DIAGNOSE_STATUS.pop(ereignis, None)
        if vorher is not None:
            if vorher[2]:
                logger.log(stufe, "%s zustand=%s wiederholungen=%d", ereignis, vorher[0], vorher[2], stacklevel=2)
            logger.info("%s zustand=wiederhergestellt", ereignis, stacklevel=2)


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
