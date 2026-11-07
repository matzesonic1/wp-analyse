"""Kommandozeilenprogramm für das Home-Assistant-Monitoring."""

import argparse
import logging
import math
import os
import signal
import threading
from collections.abc import Sequence

from wpanalyse.adapters.novelan_ladv9 import NovelanLadv9Adapter
from wpanalyse.logging_config import konfiguriere_logging
from wpanalyse.monitor import Monitor
from wpanalyse.speicher.sqlite import SQLiteSpeicher

log = logging.getLogger("wpanalyse.ha_monitor")


def _intervall(wert: str) -> float:
    """Liest ein positives, endliches Polling-Intervall."""
    try:
        intervall = float(wert)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Das Intervall muss eine Zahl sein.") from exc
    if not math.isfinite(intervall) or intervall <= 0:
        raise argparse.ArgumentTypeError("Das Intervall muss größer als 0 sein.")
    return intervall


def main(argv: Sequence[str] | None = None) -> int:
    """Startet das Home-Assistant-Monitoring und beendet es geordnet."""
    parser = argparse.ArgumentParser(description="Home-Assistant-Monitoring (nur lesend)")
    parser.add_argument(
        "--db",
        default=os.environ.get("WPANALYSE_DB", "data/wp.sqlite"),
        help="Pfad der SQLite-Datenbank",
    )
    parser.add_argument(
        "--intervall",
        "--interval",
        type=_intervall,
        default=_intervall(os.environ.get("WPANALYSE_INTERVAL", "60")),
        help="Abfrageintervall in Sekunden (mindestens 60)",
    )
    parser.add_argument("--einmal", action="store_true", help="nur eine Abfrage ausführen")
    args = parser.parse_args(argv)

    try:
        konfiguriere_logging()
        log.info("Home-Assistant-Monitor wird gestartet")
        adapter = NovelanLadv9Adapter()
        with SQLiteSpeicher(args.db) as speicher:
            monitor = Monitor(adapter, speicher, args.intervall, min_intervall_s=60.0)
            if args.einmal:
                ergebnis = 0 if monitor.einmal() else 1
                log.info("Home-Assistant-Monitor beendet")
                return ergebnis

            stop_event = threading.Event()
            vorherige_handler = {}

            def beenden(_signal_nummer: int, _frame: object) -> None:
                """Fordert ein zeitnahes Beenden nach der laufenden Abfrage an."""
                stop_event.set()

            try:
                for signal_nummer in (signal.SIGINT, signal.SIGTERM):
                    vorherige_handler[signal_nummer] = signal.signal(signal_nummer, beenden)
                monitor.laufen(stop=stop_event.is_set, schlafen=stop_event.wait)
            finally:
                for signal_nummer, handler in vorherige_handler.items():
                    signal.signal(signal_nummer, handler)
            if stop_event.is_set():
                log.info("Monitoring geordnet beendet")
        return 0
    except Exception as exc:  # noqa: BLE001 - Fehlertexte könnten Zugangsdaten enthalten.
        # Fehlertexte können von Drittbibliotheken stammen; nur den Typ ausgeben.
        log.error("Home-Assistant-Monitor konnte nicht gestartet werden (%s)", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
