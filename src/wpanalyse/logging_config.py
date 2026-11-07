"""Gemeinsame und sichere Logkonfiguration für die Kommandozeilenprogramme."""

import logging
import os
import re

_FORMAT = "%(asctime)s %(levelname)s %(message)s"
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


def konfiguriere_logging(stufe: str | None = None) -> None:
    """Konfiguriert einheitliche Logs; die Stufe kann per Umgebung gesetzt werden."""
    name = (stufe if stufe is not None else os.environ.get("WPANALYSE_LOG_LEVEL", "INFO")).upper()
    level = logging.getLevelName(name)
    if not isinstance(level, int):
        raise ValueError("Unbekannte Logstufe")  # noqa: TRY004 - Der Logstufenwert ist ungültig.

    logging.basicConfig(level=level, format=_FORMAT)
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers:
        if _geheimnis_filter not in handler.filters:
            handler.addFilter(_geheimnis_filter)
