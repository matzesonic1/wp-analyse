"""Gemeinsame, sichere Konfiguration für Anwendungslogs."""

import logging
import os
import sys

_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_LOGGER_NAMEN = ("wpanalyse.monitor", "wpanalyse.ha_monitor", "wpanalyse.run")


class _GeheimnisFilter(logging.Filter):
    """Entfernt Zugangstoken und Fehlerdetails aus Logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redigiert bekannte Token und unterdrückt Tracebacks."""
        try:
            nachricht = record.getMessage()
        except Exception:  # noqa: BLE001 - Logformatierungsfehler dürfen keine Details ausgeben.
            nachricht = "Logeintrag konnte nicht formatiert werden"
        for name in ("HA_TOKEN", "NTFY_TOKEN"):
            geheimnis = os.environ.get(name, "")
            if geheimnis:
                nachricht = nachricht.replace(geheimnis, "[GEHEIM]")
        record.msg = nachricht
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        return True


_geheimnis_filter = _GeheimnisFilter()


def konfiguriere_logging(stufe: str | None = None) -> None:
    """Richtet stdout-Logging mit INFO-Standard und optionaler Umgebungsstufe ein."""
    name = stufe if stufe is not None else os.environ.get("WPANALYSE_LOG_LEVEL", "INFO")
    level = logging.getLevelName(name.upper())
    if not isinstance(level, int):
        raise ValueError("Ungültige Log-Stufe")  # noqa: TRY004 - Der übergebene Typ ist korrekt.

    root = logging.getLogger()
    root.setLevel(level)
    handler = next(
        (handler for handler in root.handlers if getattr(handler, "_wpanalyse_handler", False)),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler.addFilter(_geheimnis_filter)
        handler._wpanalyse_handler = True
        root.addHandler(handler)
    handler.setLevel(level)

    for logger_name in _LOGGER_NAMEN:
        logger = logging.getLogger(logger_name)
        if _geheimnis_filter not in logger.filters:
            logger.addFilter(_geheimnis_filter)
