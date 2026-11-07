"""Monitoring: fragt die Wärmepumpe in festem Intervall ab und speichert in SQLite.

Start: ``python -m wpanalyse.monitor`` (Host über ``LUXTRONIK_HOST``).
Das Intervall beträgt mindestens 60 Sekunden, um den Regler zu schonen.
"""

import argparse
import logging
import time
from collections.abc import Callable

from wpanalyse.adapters.base import DatenAdapter
from wpanalyse.config import LuxtronikConfig
from wpanalyse.logging_config import konfiguriere_logging
from wpanalyse.speicher.sqlite import SQLiteSpeicher

log = logging.getLogger("wpanalyse.monitor")


class Monitor:
    """Pollt einen Adapter periodisch und persistiert jede Messung."""

    def __init__(
        self,
        adapter: DatenAdapter,
        speicher: SQLiteSpeicher,
        intervall_s: float = 60.0,
        min_intervall_s: float = 60.0,
    ):
        """Begrenzt das Intervall nach unten auf ``min_intervall_s``."""
        self._adapter = adapter
        self._speicher = speicher
        self.intervall_s = max(intervall_s, min_intervall_s)

    def einmal(self) -> bool:
        """Fragt einmal ab und speichert; Fehler werden geloggt und nicht geworfen."""
        try:
            df = self._adapter.aktuell()
            if df.empty:
                log.warning("Keine Messwerte empfangen, nächster Versuch im Intervall")
                return False
            self._speicher.speichern(df)
        except Exception as exc:  # noqa: BLE001 - Adapter und Speicher können unterschiedliche Fehler werfen.
            log.error(
                "Abfrage fehlgeschlagen, nächster Versuch im Intervall (%s)",
                type(exc).__name__,
            )
            return False
        log.info("Messung gespeichert: %s", df.index[0].isoformat())
        return True

    def laufen(
        self,
        stop: Callable[[], bool] = lambda: False,
        schlafen: Callable[[float], None] = time.sleep,
    ) -> None:
        """Läuft bis ``stop()`` wahr ist; zwischen zwei Abfragen liegt das Intervall."""
        while not stop():
            start = time.monotonic()
            self.einmal()
            if stop():
                break
            schlafen(max(0.0, self.intervall_s - (time.monotonic() - start)))


def main() -> None:
    """Kommandozeile: Dauerbetrieb oder mit ``--einmal`` eine einzelne Abfrage."""
    from wpanalyse.adapters.luxtronik import LuxtronikAdapter

    parser = argparse.ArgumentParser(description="Luxtronik-Monitoring (nur lesend)")
    parser.add_argument("--db", default="data/wp.sqlite", help="Pfad der SQLite-Datenbank")
    parser.add_argument("--intervall", type=float, default=60.0, help="Sekunden (mindestens 60)")
    parser.add_argument("--einmal", action="store_true", help="nur eine Abfrage")
    args = parser.parse_args()

    try:
        konfiguriere_logging()
        log.info("Monitoring gestartet")
        config = LuxtronikConfig.aus_umgebung()
        with SQLiteSpeicher(args.db) as speicher:
            monitor = Monitor(
                LuxtronikAdapter(config),
                speicher,
                args.intervall,
                config.min_intervall_s,
            )
            if args.einmal:
                monitor.einmal()
                log.info("Monitoring beendet")
                return
            monitor.laufen()
    except KeyboardInterrupt:
        log.info("Monitoring beendet")
    except Exception as exc:  # noqa: BLE001 - Startfehler werden ohne Details protokolliert.
        log.error("Monitoring fehlgeschlagen (%s)", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
