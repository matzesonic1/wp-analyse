import logging
import sys
from datetime import UTC, date, datetime, time

import pandas as pd
import pytest

from wpanalyse import dashboard, logging_config
from wpanalyse.dashboard import (
    berechne_az_nach_aussentemperatur,
    berechne_starts_pro_tag,
    bereite_auswahl_vor,
    numerische_spalten,
)
from wpanalyse.simulation import simuliere
from wpanalyse.speicher.sqlite import SQLiteSpeicher


@pytest.fixture
def _dashboard_logging_zuruecksetzen(monkeypatch):
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


class _StreamlitFake:
    def __init__(self):
        self.session_state = {}
        self.sidebar = _SidebarFake(self)

    def set_page_config(self, **kwargs):
        pass

    def title(self, text):
        pass

    def caption(self, text):
        pass


class _SidebarFake:
    def __init__(self, st):
        self.st = st
        self.widgets = {}

    def checkbox(self, label, **kwargs):
        self.widgets[label] = kwargs

    def selectbox(self, label, options, **kwargs):
        self.widgets[label] = {**kwargs, "options": options}

    def radio(self, label, options):
        return "Simulation"


def test_reglerabfrage_uebergibt_host_und_port_an_adapter(monkeypatch):
    erfasste_konfigurationen = []

    class AdapterFake:
        def __init__(self, config):
            erfasste_konfigurationen.append(config)

    class MonitorFake:
        def __init__(self, adapter, speicher, intervall_s):
            pass

        def einmal(self):
            return True

    monkeypatch.setattr(dashboard, "lade_live_daten", lambda speicher, stunden: pd.DataFrame())
    monkeypatch.setattr("wpanalyse.adapters.luxtronik.LuxtronikAdapter", AdapterFake)
    monkeypatch.setattr("wpanalyse.monitor.Monitor", MonitorFake)

    status = dashboard.frage_regler_ab(object(), "regler.example", 12345, 60)

    assert status == "Abfrage erfolgreich"
    assert erfasste_konfigurationen[0].host == "regler.example"
    assert erfasste_konfigurationen[0].port == 12345


def test_freie_auswahl_erkennt_zahlen_und_bool():
    index = pd.date_range("2026-01-10", periods=2, freq="min", tz="UTC")
    df = pd.DataFrame(
        {"a_c": [1.0, 2.0], "an": [True, False], "text": ["x", "y"], "leer": [None, None]}, index=index
    )

    assert numerische_spalten(df) == ["a_c", "an"]
    daten = bereite_auswahl_vor(df, ["a_c", "an"])
    assert daten["an"].tolist() == [1.0, 0.0]


def test_starts_aus_regler_zaehler():
    index = pd.date_range("2026-01-10 23:58", periods=4, freq="min", tz="UTC")
    df = pd.DataFrame({"verdichter_starts_zaehler": [100, 101, 101, 102]}, index=index)

    starts = berechne_starts_pro_tag(df)

    assert starts.to_dict() == {
        pd.Timestamp("2026-01-10", tz="UTC"): 1,
        pd.Timestamp("2026-01-11", tz="UTC"): 1,
    }


def test_starts_werden_pro_utc_tag_gezaehlt():
    index = pd.date_range("2026-01-10 23:58", periods=5, freq="min", tz="UTC")
    df = pd.DataFrame({"verdichter_an": [False, True, True, False, True]}, index=index)

    starts = berechne_starts_pro_tag(df)

    assert starts.to_dict() == {
        pd.Timestamp("2026-01-10", tz="UTC"): 1,
        pd.Timestamp("2026-01-11", tz="UTC"): 1,
    }


def test_az_wird_mit_tagesmittel_der_aussentemperatur_verbunden():
    index = pd.date_range("2026-01-10", periods=3, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "aussen_c": [-5.0, -3.0, -1.0],
            "leistung_w": [1000.0, 2000.0, 0.0],
            "waerme_w": [3000.0, 6000.0, 0.0],
        },
        index=index,
    )

    az_nach_aussen = berechne_az_nach_aussentemperatur(df)

    assert az_nach_aussen.loc[pd.Timestamp("2026-01-10", tz="UTC"), "aussen_c"] == -3.0
    assert az_nach_aussen.loc[pd.Timestamp("2026-01-10", tz="UTC"), "az"] == 3.0


def test_simulationsdaten_enthalten_alle_dashboard_trends():
    df = simuliere(tage=2)

    starts = berechne_starts_pro_tag(df)
    az_nach_aussen = berechne_az_nach_aussentemperatur(df)

    assert len(starts) == 2
    assert (starts > 0).all()
    assert list(az_nach_aussen.columns) == ["aussen_c", "az"]
    assert len(az_nach_aussen) == 2


class _HeissgasFake:
    def __init__(self):
        self.charts = []
        self.tables = []
        self.infos = []
        self.captions = []

    def subheader(self, text):
        pass

    def caption(self, text):
        self.captions.append(text)

    def altair_chart(self, chart, **kwargs):
        self.charts.append((chart, kwargs))

    def dataframe(self, data):
        self.tables.append(data)

    def info(self, text):
        self.infos.append(text)


def test_heissgas_verlauf_zeigt_temperaturen_und_zeitgleichen_kontext():
    index = pd.date_range("2026-01-10", periods=3, freq="min", tz="UTC")
    df = pd.DataFrame(
        {
            "heissgas_c": [50.0, None, 60.0],
            "aussen_c": [3.0, 3.5, 4.0],
            "vorlauf_c": [35.0, 36.0, 37.0],
            "ruecklauf_c": [30.0, 31.0, 32.0],
            "verdichter_an": [True, None, False],
            "verdichter_laufzeit_s": [60, None, 0],
            "betriebsart": ["heizen", None, "aus"],
        },
        index=index,
    )
    st = _HeissgasFake()

    dashboard.zeige_heissgas_verlauf(st, df)

    chart, optionen = st.charts[0]
    spezifikation = chart.to_dict()
    temperaturdiagramm, betriebsartdiagramm = spezifikation["vconcat"]
    linie, punkte, hover = temperaturdiagramm["layer"]
    assert linie["mark"]["type"] == "line"
    assert punkte["mark"]["type"] == "circle"
    assert punkte["mark"]["size"] == 20
    assert hover["mark"]["type"] == "circle"
    assert {feld["field"] for feld in hover["encoding"]["tooltip"]} == {
        "zeit", "messreihe", "temperatur", "Betriebsart", "Verdichter",
    }
    assert hover["encoding"]["tooltip"][0]["format"] == "%d.%m.%Y %H:%M:%S"
    assert betriebsartdiagramm["encoding"]["y"]["field"] == "Betriebsart"
    assert optionen["width"] == "stretch"
    daten = chart.vconcat[0].data
    assert daten["messreihe"].unique().tolist() == ["Heißgas", "Außen", "Vorlauf", "Rücklauf"]
    heissgas = daten[daten["messreihe"] == "Heißgas"].set_index("zeit")
    assert pd.isna(heissgas.loc[index[1], "temperatur"])
    assert heissgas.loc[index[0], "Betriebsart"] == "heizen"
    assert heissgas.loc[index[1], "Betriebsart"] == "unbekannt"
    assert heissgas.loc[index[1], "Verdichter"] == "unbekannt"
    assert heissgas.loc[index[2], "Verdichter"] == "aus"
    assert st.tables[0].index.tolist() == list(reversed(index))
    assert st.tables[0].loc[index[0], "betriebsart"] == "heizen"
    assert st.tables[0].loc[index[0], "verdichter_laufzeit_s"] == 60
    assert pd.isna(st.tables[0].loc[index[1], "verdichter_an"])
    assert any("Messlücken" in caption for caption in st.captions)
    assert any("keinen Verdichterschaden" in caption for caption in st.captions)


@pytest.mark.parametrize("df", [pd.DataFrame({"vorlauf_c": [30]}), pd.DataFrame({"heissgas_c": [None]})])
def test_heissgas_verlauf_behandelt_fehlende_werte(df):
    st = _HeissgasFake()
    dashboard.zeige_heissgas_verlauf(st, df)
    assert len(st.infos) == 1
    assert not st.charts
    assert not st.tables


def test_heissgas_verlauf_funktioniert_ohne_optionalen_kontext():
    st = _HeissgasFake()
    dashboard.zeige_heissgas_verlauf(st, pd.DataFrame({"heissgas_c": [55.0]}))
    chart = st.charts[0][0]
    daten = chart.vconcat[0].data
    assert daten["messreihe"].unique().tolist() == ["Heißgas"]
    assert daten["Betriebsart"].tolist() == ["unbekannt"]
    assert daten["Verdichter"].tolist() == ["unbekannt"]
    assert st.tables[0].columns.tolist() == ["heissgas_c"]


def test_logging_steuerung_bleibt_ueber_dashboard_reruns_prozessweit(monkeypatch, _dashboard_logging_zuruecksetzen):
    erster_lauf = _StreamlitFake()
    monkeypatch.setitem(sys.modules, "streamlit", erster_lauf)
    monkeypatch.setattr(dashboard, "zeige_diagramme", lambda st, df: None)
    monkeypatch.setattr(dashboard, "simuliere", lambda tage: pd.DataFrame())
    logging_config.setze_dashboard_logging(aktiviert=True, stufe="WARNING")

    dashboard.main()

    assert erster_lauf.session_state[dashboard._LOGGING_AKTIV_SCHLUESSEL] is True
    assert erster_lauf.session_state[dashboard._LOGGING_STUFE_SCHLUESSEL] == "WARNING"
    steuerung = erster_lauf.sidebar.widgets["Anwendungslogs"]
    erster_lauf.session_state[steuerung["key"]] = False
    steuerung["on_change"](*steuerung["args"])
    assert logging_config.dashboard_logging_einstellungen() == (False, "WARNING")

    zweiter_lauf = _StreamlitFake()
    monkeypatch.setitem(sys.modules, "streamlit", zweiter_lauf)
    dashboard.main()

    assert zweiter_lauf.session_state[dashboard._LOGGING_AKTIV_SCHLUESSEL] is False
    assert zweiter_lauf.sidebar.widgets["Logstufe"]["disabled"] is True


def test_fester_zeitraum_wandelt_berliner_zeit_in_utc_um():
    von, bis = dashboard.fester_zeitraum_utc(date(2026, 1, 10), time(12), date(2026, 1, 10), time(13))
    assert von == datetime(2026, 1, 10, 11, tzinfo=UTC)
    assert bis == datetime(2026, 1, 10, 12, tzinfo=UTC)
    assert dashboard.lokaler_zeitpunkt_utc(date(2026, 7, 10), time(12)) == datetime(
        2026, 7, 10, 10, tzinfo=UTC
    )


@pytest.mark.parametrize(
    ("tag", "zeit", "meldung"),
    [
        (date(2026, 3, 29), time(2, 30), "existiert"),
        (date(2026, 10, 25), time(2, 30), "doppelt"),
    ],
)
def test_lokaler_zeitpunkt_lehnt_ungueltige_zeitumstellung_ab(tag, zeit, meldung):
    with pytest.raises(ValueError, match=meldung):
        dashboard.lokaler_zeitpunkt_utc(tag, zeit)


@pytest.mark.parametrize("ende", [time(11), time(12)])
def test_fester_zeitraum_lehnt_umgekehrte_oder_gleiche_grenzen_ab(ende):
    with pytest.raises(ValueError, match="Ende muss nach dem Beginn"):
        dashboard.fester_zeitraum_utc(date(2026, 1, 10), time(12), date(2026, 1, 10), ende)


def test_zeitraum_daten_enthalten_beginn_aber_nicht_ende():
    index = pd.date_range("2026-01-10 10:59", periods=4, freq="min", tz="UTC")
    with SQLiteSpeicher(":memory:") as speicher:
        speicher.speichern(pd.DataFrame({"heissgas_c": [1, 2, 3, 4]}, index=index))
        von, bis = dashboard.fester_zeitraum_utc(date(2026, 1, 10), time(12), date(2026, 1, 10), time(12, 2))
        daten = dashboard.lade_zeitraum_daten(speicher, von, bis)
        leer = dashboard.lade_zeitraum_daten(speicher, bis + pd.Timedelta(minutes=1), bis + pd.Timedelta(minutes=2))
    assert daten.index.tolist() == index[1:3].tolist()
    assert leer.empty


def test_historische_verdichterbewertung_verwendet_messzeit(monkeypatch):
    index = pd.DatetimeIndex(["2026-01-10 11:00"], tz="UTC")
    df = pd.DataFrame({"verdichter_starts_zaehler": [100], "verdichter_betriebszeit_s": [3600]}, index=index)
    erfasste_zeit = []

    def bewerte(starts, betriebszeit, zeitpunkt, config, verlauf):
        erfasste_zeit.append(zeitpunkt)
        raise RuntimeError("Zeitpunkt erfasst")

    monkeypatch.setattr(dashboard, "bewerte_verdichter", bewerte)
    with pytest.raises(RuntimeError, match="Zeitpunkt erfasst"):
        dashboard.zeige_verdichter_bewertung(_HeissgasFake(), df, historisch=True)
    assert erfasste_zeit == [index[0]]

    df.index = pd.DatetimeIndex(["2025-01-01"], tz="UTC")
    st = _HeissgasFake()
    dashboard.zeige_verdichter_bewertung(st, df, historisch=True)
    assert "vor dem frühesten Tauschtermin" in st.infos[0]


def test_zeitraumauswahl_im_dashboard_und_abfrage_bei_ungueltigem_zeitraum(
    monkeypatch, _dashboard_logging_zuruecksetzen
):
    from streamlit.testing.v1 import AppTest

    index = pd.date_range("2026-01-10 11:00", periods=3, freq="min", tz="UTC")
    daten = pd.DataFrame({"heissgas_c": [1, 2, 3], "vorlauf_c": [30, 31, 32]}, index=index)
    abfragen = []
    anzeigen = []

    class SpeicherFake:
        def __init__(self, pfad):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def lese(self, von, bis):
            return daten[(daten.index >= von) & (daten.index < bis)]

    monkeypatch.setattr(dashboard, "SQLiteSpeicher", SpeicherFake)
    monkeypatch.setattr(dashboard, "frage_regler_ab", lambda *args: abfragen.append(1) or "Test")
    echte_diagramme = dashboard.zeige_diagramme
    monkeypatch.setattr(dashboard, "zeige_diagramme", lambda st, df, historisch=False: anzeigen.append((df, historisch)))
    app = AppTest.from_string("from wpanalyse.dashboard import main\nmain()").run()
    assert not app.exception
    assert app.sidebar.radio[1].value == "Letzte Stunden"
    assert app.sidebar.slider[0].value == 6
    assert len(abfragen) == 1

    app.sidebar.radio[1].set_value("Fester Zeitraum").run()
    app.sidebar.date_input[0].set_value(date(2026, 1, 10))
    app.sidebar.time_input[0].set_value(time(12, 0))
    app.sidebar.date_input[1].set_value(date(2026, 1, 10))
    app.sidebar.time_input[1].set_value(time(12, 2))
    app.run()
    assert not app.exception
    assert anzeigen[-1][0].index.tolist() == index[:2].tolist()
    assert anzeigen[-1][1] is True

    monkeypatch.setattr(dashboard, "zeige_diagramme", echte_diagramme)
    app.run()
    assert not app.exception
    assert any("Letzte Werte im Zeitraum" in titel.value for titel in app.subheader)
    assert app.sidebar.time_input[0].value == time(12)
    assert app.sidebar.time_input[1].value == time(12, 2)

    app.sidebar.time_input[1].set_value(time(12, 0)).run()
    assert "Ende muss nach dem Beginn" in app.error[0].value
    assert len(abfragen) == 5

    app.sidebar.time_input[0].set_value(time(13)).run()
    app.sidebar.time_input[1].set_value(time(14)).run()
    assert any("Keine Messwerte" in info.value for info in app.info)
    assert len(abfragen) == 7
