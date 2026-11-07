"""Verbindet Sammeln, Regelprüfung und Tagesberichte im Dauerbetrieb."""

import argparse
import logging
import math
import os
import signal
import threading
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from datetime import time as datetime_time
from pathlib import Path

from .adapters.novelan_ladv9 import NovelanLadv9Adapter
from .alarm import AlarmManager
from .alarm.melder import NtfyMelder
from .config import Config
from .erfassung import sammle_und_speichere
from .logging_config import konfiguriere_logging
from .monitoring import pruefe_und_melde
from .speicher.sqlite import SQLiteSpeicher
from .tageslauf import erzeuge_tagesbericht

log = logging.getLogger("wpanalyse.run")
_REGELINTERVALL_S = 15 * 60
_PRUEFZEITRAUM = timedelta(days=31)


def _intervall(wert: str) -> float:
    """Liest ein positives, endliches Sammelintervall in Sekunden."""
    try:
        sekunden = float(wert)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Das Intervall muss eine Zahl sein.") from exc
    if not math.isfinite(sekunden) or sekunden <= 0:
        raise argparse.ArgumentTypeError("Das Intervall muss größer als 0 sein.")
    return sekunden


class _LogMelder:
    """Gibt Befunde aus, wenn kein Benachrichtigungskanal konfiguriert ist."""

    def sende(self, nachricht: str) -> None:
        """Schreibt einen Befund ins Anwendungslog."""
        log.warning("%s", nachricht)


class Scheduler:
    """Plant Sammeln, Regelprüfung und tägliche Berichte mit austauschbaren Aktionen."""

    def __init__(
        self,
        adapter,
        speicher: SQLiteSpeicher,
        alarm_manager: AlarmManager,
        cfg: Config,
        bericht_ordner: Path,
        intervall_s: float,
        uhr: Callable[[], datetime] | None = None,
        warten: Callable[[float], None] | None = None,
        sammeln: Callable = sammle_und_speichere,
        pruefen: Callable = pruefe_und_melde,
        bericht: Callable = erzeuge_tagesbericht,
    ) -> None:
        """Initialisiert Abhängigkeiten und prüft das konfigurierbare Intervall."""
        if not math.isfinite(intervall_s) or intervall_s <= 0:
            raise ValueError("Das Intervall muss eine positive, endliche Zahl sein.")
        self.adapter = adapter
        self.speicher = speicher
        self.alarm_manager = alarm_manager
        self.cfg = cfg
        self.bericht_ordner = bericht_ordner
        self.intervall_s = intervall_s
        self.uhr = uhr or (lambda: datetime.now(UTC))
        self.warten = warten or time.sleep
        self.sammeln = sammeln
        self.pruefen = pruefen
        self.bericht = bericht

    def laufen(self, stop: Callable[[], bool] = lambda: False) -> None:
        """Führt fällige Läufe aus und wartet bis zum nächsten Termin."""
        jetzt = self._jetzt()
        letzte_sammlung = jetzt - timedelta(seconds=self.intervall_s)
        naechste_sammlung = jetzt
        naechste_pruefung = jetzt
        naechster_bericht = datetime.combine(
            jetzt.date() + timedelta(days=1), datetime_time.min, tzinfo=UTC
        )

        while not stop():
            jetzt = self._jetzt()
            if jetzt >= naechste_sammlung:
                self.sammeln(self.adapter, self.speicher, letzte_sammlung, jetzt)
                letzte_sammlung = jetzt
                naechste_sammlung = jetzt + timedelta(seconds=self.intervall_s)
                log.info("Messwerte gesammelt")
                if stop():
                    break

            if jetzt >= naechste_pruefung:
                self.pruefen(
                    self.speicher,
                    self.alarm_manager,
                    self.cfg,
                    jetzt - _PRUEFZEITRAUM,
                    jetzt,
                )
                naechste_pruefung = jetzt + timedelta(seconds=_REGELINTERVALL_S)
                log.info("Regelprüfung abgeschlossen")
                if stop():
                    break

            while naechster_bericht <= jetzt:
                tag = naechster_bericht.date() - timedelta(days=1)
                self.bericht(
                    self.speicher,
                    self.cfg,
                    tag,
                    self.bericht_ordner / f"{tag.isoformat()}.md",
                )
                log.info("Tagesbericht für %s erzeugt", tag.isoformat())
                naechster_bericht += timedelta(days=1)
                if stop():
                    break

            if stop():
                break
            naechster_termin = min(naechste_sammlung, naechste_pruefung, naechster_bericht)
            self.warten(max(0.0, (naechster_termin - self._jetzt()).total_seconds()))

    def _jetzt(self) -> datetime:
        """Liefert eine zonierte UTC-Zeit für stabile Intervallvergleiche."""
        zeitpunkt = self.uhr()
        if zeitpunkt.tzinfo is None or zeitpunkt.utcoffset() is None:
            raise ValueError("Die Scheduler-Uhr muss eine zonierte Zeit liefern.")
        return zeitpunkt.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    """Startet den Dauerbetrieb und beendet ihn bei SIGINT oder SIGTERM."""
    parser = argparse.ArgumentParser(description="Wärmepumpen-Dauerbetrieb")
    parser.add_argument(
        "--db",
        default=os.environ.get("WPANALYSE_DB", "data/wp.sqlite"),
        help="Pfad der SQLite-Datenbank",
    )
    parser.add_argument(
        "--intervall",
        type=_intervall,
        default=os.environ.get("WPANALYSE_INTERVAL", "60"),
        help="Sammelintervall in Sekunden (Standard: 60)",
    )
    parser.add_argument(
        "--bericht-ordner",
        default=os.environ.get("WPANALYSE_REPORT_DIR", "reports"),
        help="Zielordner für Tagesberichte",
    )
    args = parser.parse_args(argv)

    try:
        konfiguriere_logging()
        log.info("Dauerbetrieb wird gestartet")
        adapter = NovelanLadv9Adapter()
        melder = NtfyMelder() if os.environ.get("NTFY_TOPIC") else _LogMelder()
        bericht_ordner = Path(args.bericht_ordner)
        bericht_ordner.mkdir(parents=True, exist_ok=True)
        with SQLiteSpeicher(args.db) as speicher:
            scheduler = Scheduler(
                adapter,
                speicher,
                AlarmManager(melder),
                Config(),
                bericht_ordner,
                args.intervall,
            )
            stop_event = threading.Event()
            vorherige_handler = {}

            def beenden(_signal_nummer: int, _frame: object) -> None:
                """Fordert das geordnete Beenden nach dem laufenden Schritt an."""
                stop_event.set()

            try:
                for signal_nummer in (signal.SIGINT, signal.SIGTERM):
                    vorherige_handler[signal_nummer] = signal.signal(signal_nummer, beenden)
                scheduler.laufen(stop=stop_event.is_set)
            finally:
                for signal_nummer, handler in vorherige_handler.items():
                    signal.signal(signal_nummer, handler)
        log.info("Dauerbetrieb geordnet beendet")
        return 0
    except KeyboardInterrupt:
        log.info("Dauerbetrieb durch Benutzer beendet")
        return 0
    except Exception as exc:  # noqa: BLE001 - Laufzeitfehler erhalten einen sichtbaren Fehlerstatus.
        log.error("Dauerbetrieb fehlgeschlagen (%s)", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
