import pandas as pd

from wpanalyse import dashboard
from wpanalyse.dashboard import (
    berechne_az_nach_aussentemperatur,
    berechne_starts_pro_tag,
    bereite_auswahl_vor,
    numerische_spalten,
)
from wpanalyse.simulation import simuliere


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
