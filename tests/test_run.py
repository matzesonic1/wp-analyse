"""Tests für den integrierten Scheduler und seine Kommandozeile."""

import logging
import signal
from datetime import UTC, datetime, timedelta

import pytest

from wpanalyse import run


class _Uhr:
    """Uhr, die ausschließlich durch die Fake-Wartefunktion fortschreitet."""

    def __init__(self, zeitpunkt: datetime):
        self.zeitpunkt = zeitpunkt

    def jetzt(self) -> datetime:
        return self.zeitpunkt

    def warten(self, sekunden: float) -> None:
        self.zeitpunkt += timedelta(seconds=sekunden)


def test_scheduler_sammelt_minutlich_und_prueft_alle_15_minuten(tmp_path):
    """Fake-Zeit belegt beide Intervalle und stoppt direkt nach der fälligen Prüfung."""
    uhr = _Uhr(datetime(2026, 1, 2, 12, tzinfo=UTC))
    sammlungen = []
    pruefungen = []

    def sammeln(_adapter, _speicher, von, bis):
        sammlungen.append((von, bis))

    def pruefen(_speicher, _alarm_manager, _cfg, von, bis):
        pruefungen.append((von, bis))

    scheduler = run.Scheduler(
        object(),
        object(),
        object(),
        object(),
        tmp_path,
        intervall_s=60,
        uhr=uhr.jetzt,
        warten=uhr.warten,
        sammeln=sammeln,
        pruefen=pruefen,
        bericht=lambda *_args: pytest.fail("Vor Mitternacht darf kein Bericht entstehen"),
    )

    scheduler.laufen(stop=lambda: bool(pruefungen and uhr.jetzt() >= pruefungen[0][1] + timedelta(minutes=15)))

    assert len(sammlungen) == 16
    assert sammlungen[0] == (
        datetime(2026, 1, 2, 11, 59, tzinfo=UTC),
        datetime(2026, 1, 2, 12, tzinfo=UTC),
    )
    assert all(bis - von == timedelta(minutes=1) for von, bis in sammlungen)
    assert [bis for _von, bis in pruefungen] == [
        datetime(2026, 1, 2, 12, tzinfo=UTC),
        datetime(2026, 1, 2, 12, 15, tzinfo=UTC),
    ]
    assert all(bis - von == timedelta(days=31) for von, bis in pruefungen)


def test_scheduler_erzeugt_bericht_fuer_abgeschlossenen_utc_tag(tmp_path):
    """Der UTC-Tageswechsel löst einmal den Bericht des Vortags aus."""
    uhr = _Uhr(datetime(2026, 1, 2, 23, 59, 30, tzinfo=UTC))
    berichte = []

    def bericht(_speicher, _cfg, tag, ziel):
        berichte.append((tag, ziel))

    scheduler = run.Scheduler(
        object(),
        object(),
        object(),
        object(),
        tmp_path,
        intervall_s=3600,
        uhr=uhr.jetzt,
        warten=uhr.warten,
        sammeln=lambda *_args: None,
        pruefen=lambda *_args: None,
        bericht=bericht,
    )

    scheduler.laufen(stop=lambda: bool(berichte))

    assert berichte == [(datetime(2026, 1, 2, tzinfo=UTC).date(), tmp_path / "2026-01-02.md")]


def test_scheduler_laufzeitfehler_werden_weitergegeben(tmp_path):
    """Ein fehlgeschlagener Sammellauf wird nicht als erfolgreicher Zyklus behandelt."""
    def sammeln(*_args):
        raise OSError("Speicher nicht verfügbar")

    scheduler = run.Scheduler(
        object(),
        object(),
        object(),
        object(),
        tmp_path,
        intervall_s=60,
        uhr=lambda: datetime(2026, 1, 2, tzinfo=UTC),
        warten=lambda _sekunden: pytest.fail("Nach einem Fehler darf nicht gewartet werden"),
        sammeln=sammeln,
    )

    with pytest.raises(OSError, match="Speicher nicht verfügbar"):
        scheduler.laufen()


def test_main_konfiguriert_scheduler_und_beendet_geordnet(monkeypatch, tmp_path):
    """Die CLI übergibt Optionen und behandelt SIGTERM mit restaurierten Handlern."""
    monkeypatch.setenv("HA_URL", "http://ha.test")
    monkeypatch.setenv("HA_TOKEN", "test-token")
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    scheduler_werte = {}
    handler = {}
    zurueckgesetzt = []
    vorheriger_handler = object()

    class _Adapter:
        pass

    class _Scheduler:
        def __init__(self, _adapter, _speicher, _alarm, _cfg, bericht_ordner, intervall_s):
            scheduler_werte.update(bericht_ordner=bericht_ordner, intervall_s=intervall_s)

        def laufen(self, stop):
            assert stop()

    def signal_mock(signal_nummer, neuer_handler):
        if neuer_handler is vorheriger_handler:
            zurueckgesetzt.append(signal_nummer)
            return None
        handler[signal_nummer] = neuer_handler
        if signal_nummer == signal.SIGTERM:
            neuer_handler(signal_nummer, None)
        return vorheriger_handler

    monkeypatch.setattr(run, "NovelanLadv9Adapter", _Adapter)
    monkeypatch.setattr(run, "Scheduler", _Scheduler)
    monkeypatch.setattr(run.signal, "signal", signal_mock)

    ergebnis = run.main(
        [
            "--db",
            str(tmp_path / "messwerte.sqlite"),
            "--intervall",
            "90",
            "--bericht-ordner",
            str(tmp_path / "berichte"),
        ]
    )

    assert ergebnis == 0
    assert scheduler_werte == {"bericht_ordner": tmp_path / "berichte", "intervall_s": 90.0}
    assert set(handler) == {signal.SIGINT, signal.SIGTERM}
    assert set(zurueckgesetzt) == {signal.SIGINT, signal.SIGTERM}


def test_main_meldet_laufzeitfehler_und_liefert_fehlercode(caplog, monkeypatch):
    """Konfigurationsfehler sind im Log sichtbar und werden mit Fehlercode beendet."""
    monkeypatch.setattr(run, "NovelanLadv9Adapter", lambda: (_ for _ in ()).throw(ValueError()))

    with caplog.at_level(logging.ERROR):
        ergebnis = run.main([])

    assert ergebnis == 2
    assert "Dauerbetrieb fehlgeschlagen (ValueError)" in caplog.text
