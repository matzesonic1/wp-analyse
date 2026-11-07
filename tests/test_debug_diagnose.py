"""Tests für die sichere Ablaufdiagnose ohne reale Reglerzugriffe."""

import logging
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from wpanalyse import dashboard, logging_config, monitor
from wpanalyse.speicher.sqlite import SQLiteSpeicher


@pytest.fixture(autouse=True)
def diagnose_zuruecksetzen(monkeypatch):
    monkeypatch.setattr(logging_config, "_DIAGNOSE_STATUS", {})
    monkeypatch.setattr(logging_config, "_DASHBOARD_INITIALISIERT", False)


class Adapter:
    def __init__(self, resultat):
        self.resultat = resultat
        self.aufrufe = 0

    def aktuell(self):
        self.aufrufe += 1
        if isinstance(self.resultat, Exception):
            raise self.resultat
        return self.resultat


class Speicher:
    def __init__(self, fehler=None):
        self.fehler = fehler
        self.zeilen = 0

    def speichern(self, df):
        if self.fehler:
            raise self.fehler
        self.zeilen += len(df)


def messung():
    return pd.DataFrame({"vorlauf_c": [37.4]}, index=pd.DatetimeIndex(["2026-01-01"], tz="UTC"))


def test_debug_ablauf_und_info_filter(caplog):
    adapter = Adapter(messung())
    speicher = Speicher()
    with caplog.at_level(logging.DEBUG, logger="wpanalyse.monitor"):
        assert monitor.Monitor(adapter, speicher).einmal()
    assert adapter.aufrufe == 1
    assert speicher.zeilen == 1
    assert "wp_abfrage beginn" in caplog.text
    assert "wp_abfrage ende ergebnis=erfolg dauer_ms=" in caplog.text
    assert "datenbank vorgang=speichern ergebnis=ok zeilen=1" in caplog.text
    assert "37.4" not in caplog.text
    assert any(r.funcName == "einmal" and r.name == "wpanalyse.monitor" for r in caplog.records)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="wpanalyse.monitor"):
        assert monitor.Monitor(adapter, speicher).einmal()
    assert "Messung gespeichert" in caplog.text
    assert "wp_abfrage beginn" not in caplog.text


@pytest.mark.parametrize(
    ("fehler", "kategorie"),
    [
        (TimeoutError("secret 192.0.2.1"), "timeout"),
        (ConnectionError("secret 192.0.2.1"), "verbindung"),
        (ValueError("secret 192.0.2.1"), "datenformat"),
        (RuntimeError("secret 192.0.2.1"), "unbekannt"),
    ],
)
def test_adapterfehler_ohne_vertrauliche_details(caplog, fehler, kategorie):
    with caplog.at_level(logging.DEBUG, logger="wpanalyse.monitor"):
        assert not monitor.Monitor(Adapter(fehler), Speicher()).einmal()
    assert f"zustand={kategorie}" in caplog.text
    assert "wp_abfrage ende ergebnis=fehler" in caplog.text
    assert "secret" not in caplog.text
    assert "192.0.2.1" not in caplog.text
    assert "Traceback" not in caplog.text


def test_leere_messung_und_datenbankfehler(caplog):
    with caplog.at_level(logging.DEBUG, logger="wpanalyse.monitor"):
        assert not monitor.Monitor(Adapter(pd.DataFrame()), Speicher()).einmal()
        assert not monitor.Monitor(Adapter(messung()), Speicher(OSError("secret"))).einmal()
    assert "wp_abfrage ende ergebnis=leer" in caplog.text
    assert "datenbank vorgang=speichern ergebnis=fehler" in caplog.text
    assert "zustand=datenbank" in caplog.text
    assert "secret" not in caplog.text


def test_drosselung_und_wiederherstellung(caplog, monkeypatch):
    zeit = [0.0]
    monkeypatch.setattr(logging_config.time, "monotonic", lambda: zeit[0])
    logger = logging.getLogger("wpanalyse.diagnosetest")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        for _ in range(3):
            logging_config.diagnose_gedrosselt(logger, logging.ERROR, "fehler", "timeout")
        zeit[0] = 60.0
        logging_config.diagnose_gedrosselt(logger, logging.ERROR, "fehler", "timeout")
        logging_config.diagnose_gedrosselt(logger, logging.ERROR, "fehler", "datenbank")
        logging_config.diagnose_wiederhergestellt(logger, logging.ERROR, "fehler")
    assert caplog.text.count("zustand=timeout") == 2
    assert "zustand=timeout wiederholungen=3" in caplog.text
    assert "zustand=datenbank" in caplog.text
    assert "zustand=wiederhergestellt" in caplog.text


def test_dashboard_ueberspringt_abfrage_und_loggt_diagnose(caplog, monkeypatch):
    daten = pd.DataFrame({"a": [1]}, index=pd.DatetimeIndex([pd.Timestamp.now(tz="UTC")]))
    monkeypatch.setattr(dashboard, "lade_live_daten", lambda *_: daten)
    with caplog.at_level(logging.DEBUG, logger="wpanalyse.dashboard"):
        for _ in range(3):
            assert dashboard.frage_regler_ab(object(), "secret-host", 8889, 60).startswith("Letzte Messung")
    assert caplog.text.count("zustand=uebersprungen") == 1
    assert "secret-host" not in caplog.text
    assert any(r.funcName == "frage_regler_ab" for r in caplog.records)


def test_dashboard_initialisiert_nur_einmal_auch_parallel(monkeypatch, capsys):
    logger = logging.getLogger("wpanalyse")
    alter_level, alte_propagation = logger.level, logger.propagate
    alte_handler = list(logger.handlers)
    monkeypatch.setattr(logging_config, "_DASHBOARD_LOGGING_STUFE", "INFO")
    monkeypatch.setattr(logging_config, "_DASHBOARD_LOGGING_AKTIV", True)
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda _: logging_config.initialisiere_dashboard_logging(), range(10)))
        assert capsys.readouterr().out.count("Dashboard initialisiert") == 1
        assert sum(bool(getattr(h, "_wpanalyse_handler", False)) for h in logger.handlers) == 1
    finally:
        for handler in list(logger.handlers):
            if handler not in alte_handler:
                logger.removeHandler(handler)
                handler.close()
        logger.setLevel(alter_level)
        logger.propagate = alte_propagation


def test_lesen_loggt_datenbankfehler_ohne_exception_text(caplog):
    class FehlerSpeicher:
        def lese(self, von, bis):
            raise OSError("secret-host C:\\secret\\datenbank")

    with caplog.at_level(logging.DEBUG, logger="wpanalyse.dashboard"), pytest.raises(OSError):
        dashboard.lade_live_daten(FehlerSpeicher(), 1)
    assert "datenbank vorgang=lesen ergebnis=fehler" in caplog.text
    assert "zustand=datenbank" in caplog.text
    assert "secret" not in caplog.text


def test_speichert_und_liest_testdatenbank_mit_debug_ausgabe(tmp_path, caplog):
    with caplog.at_level(logging.DEBUG, logger="wpanalyse"), SQLiteSpeicher(tmp_path / "test.sqlite") as speicher:
        assert monitor.Monitor(Adapter(messung()), speicher).einmal()
        daten = dashboard.lade_live_daten(speicher, 1)
    assert daten.empty
    assert "datenbank vorgang=speichern ergebnis=ok zeilen=1" in caplog.text
    assert "datenbank vorgang=lesen ergebnis=ok zeilen=0" in caplog.text


def test_logging_einstellungen_sind_zwischen_prozessen_getrennt():
    code = (
        "import logging; from wpanalyse.logging_config import setze_dashboard_logging; "
        "setze_dashboard_logging(aktiviert=True, stufe='DEBUG'); "
        "logging.getLogger('wpanalyse.monitor').debug('dashboard debug')"
    )
    dashboard_lauf = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    cli_lauf = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import logging; from wpanalyse.logging_config import konfiguriere_logging; "
                "konfiguriere_logging('INFO'); logging.getLogger('wpanalyse.monitor').debug('cli debug')"
            ),
        ],
        capture_output=True, text=True, check=True,
    )
    assert "dashboard debug" in dashboard_lauf.stdout
    assert "cli debug" not in cli_lauf.stdout


def test_debug_ausgabe_zeigt_prozess_und_aufrufende_funktion_ohne_geheimnisse():
    code = (
        "import logging, os; "
        "from wpanalyse.logging_config import setze_dashboard_logging, diagnose_gedrosselt; "
        "setze_dashboard_logging(aktiviert=True, stufe='DEBUG'); "
        "logger = logging.getLogger('wpanalyse.dashboard'); "
        "print('erwartete_pid=' + str(os.getpid())); "
        "diagnose_gedrosselt(logger, logging.DEBUG, 'intervall entscheidung', "
        "'uebersprungen', (42, 55)); "
        "logger.info('normale meldung')"
    )
    ausgabe = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout
    pid = re.search(r"erwartete_pid=(\d+)", ausgabe)
    assert pid is not None
    assert f"DEBUG pid={pid.group(1)} quelle=wpanalyse.dashboard.<module>" in ausgabe
    assert "intervall entscheidung zustand=uebersprungen alter_s=42 grenze_s=55" in ausgabe
    info = next(zeile for zeile in ausgabe.splitlines() if "normale meldung" in zeile)
    assert "pid=" not in info
    assert "quelle=" not in info
