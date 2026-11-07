"""Tests für LuxtronikAdapter und Monitor mit einem gefälschten Regler."""

from types import SimpleNamespace
import sys

import pandas as pd
import pytest

from wpanalyse import monitor
from wpanalyse.adapters.luxtronik import LuxtronikAdapter
from wpanalyse.config import LUXTRONIK_FELDER, LuxtronikConfig
from wpanalyse.monitor import Monitor
from wpanalyse.speicher.sqlite import SQLiteSpeicher

WERTE = {
    "ID_WEB_Temperatur_TA": 6.4,
    "ID_WEB_Temperatur_TVL": 42.0,
    "ID_WEB_Temperatur_TRL": 38.6,
    "Heat_Output": 2854,
    "ID_WEB_Time_WPein_akt": 2382,
    "ID_WEB_Time_ZWE1_akt": 0,
    "ID_WEB_WP_BZ_akt": "heating",
}


class FalscherClient:
    """Liefert Calculation-Einträge aus einem Dict; unbekannte IDs ergeben ``None``."""

    def __init__(self, werte):
        """Baut das Objekt ``calculations`` mit ``get`` nach."""
        self.calculations = SimpleNamespace(
            get=lambda name: SimpleNamespace(value=werte[name]) if name in werte else None,
            calculations={
                i: SimpleNamespace(name=name, value=wert) for i, (name, wert) in enumerate(werte.items())
            }
            | {
                900: SimpleNamespace(name="Unknown_Calculation_900", value=5),
                901: SimpleNamespace(name="ID_WEB_Freq_VD", value=1742),
                902: SimpleNamespace(name="ID_WEB_Text", value="abc"),
            },
        )


def test_weitere_werte_als_lux_spalten():
    df = _adapter().aktuell()
    assert df["lux_ID_WEB_Freq_VD"].iloc[0] == 1742
    assert "lux_ID_WEB_Text" not in df.columns
    assert "lux_Unknown_Calculation_900" not in df.columns
    assert "lux_ID_WEB_Temperatur_TVL" not in df.columns


def test_weitere_werte_abschaltbar():
    config = LuxtronikConfig(host="x", alle_calculations_speichern=False)
    df = LuxtronikAdapter(config, lambda h, p: FalscherClient(WERTE)).aktuell()
    assert not any(spalte.startswith("lux_") for spalte in df.columns)


def _adapter(werte=WERTE):
    """Erzeugt einen Adapter mit gefälschtem Client."""
    return LuxtronikAdapter(LuxtronikConfig(host="127.0.0.1"), lambda host, port: FalscherClient(werte))


def test_aktuell_liefert_projektfelder_mit_utc_index():
    df = _adapter().aktuell()
    assert len(df) == 1
    assert str(df.index.tz) == "UTC"
    assert df.loc[:, "vorlauf_c"].iloc[0] == 42.0
    assert df["betriebsart"].iloc[0] == "heizen"
    assert bool(df["verdichter_an"].iloc[0]) is True
    assert bool(df["heizstab_an"].iloc[0]) is False
    assert "betriebsart_roh" not in df.columns
    assert set(LUXTRONIK_FELDER) - {"betriebsart_roh"} <= set(df.columns)


def test_fehlende_felder_werden_zu_none():
    df = _adapter({"ID_WEB_Temperatur_TA": 1.0}).aktuell()
    assert df["vorlauf_c"].iloc[0] is None
    assert bool(df["verdichter_an"].iloc[0]) is False


def test_ohne_host_fehler():
    with pytest.raises(ValueError):
        LuxtronikAdapter(LuxtronikConfig(host=""))


def test_lese_nicht_unterstuetzt():
    with pytest.raises(NotImplementedError):
        _adapter().lese(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-02"))


def test_monitor_intervall_mindestens_60s():
    with SQLiteSpeicher(":memory:") as speicher:
        assert Monitor(_adapter(), speicher, intervall_s=5).intervall_s == 60.0


def test_monitor_speichert_und_schlaeft_intervall():
    schlafzeiten = []
    aufrufe = {"n": 0}

    def stop():
        aufrufe["n"] += 1
        return aufrufe["n"] > 4  # zwei volle Runden

    with SQLiteSpeicher(":memory:") as speicher:
        Monitor(_adapter(), speicher).laufen(stop=stop, schlafen=schlafzeiten.append)
        df = speicher.lese(pd.Timestamp("2000-01-01", tz="UTC"), pd.Timestamp("2100-01-01", tz="UTC"))
    assert len(schlafzeiten) == 2
    assert all(55 < s <= 60 for s in schlafzeiten)
    assert len(df) >= 1
    assert df["vorlauf_c"].iloc[0] == 42.0


def test_monitor_faengt_fehler_ab():
    class Kaputt(LuxtronikAdapter):
        def aktuell(self):
            raise ConnectionError("Regler nicht erreichbar")

    with SQLiteSpeicher(":memory:") as speicher:
        adapter = Kaputt(LuxtronikConfig(host="x"), lambda h, p: None)
        assert Monitor(adapter, speicher).einmal() is False


def test_monitor_behandelt_leere_messreihe_ohne_exception(caplog):
    class LeererAdapter:
        def aktuell(self):
            return pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC"))

    with SQLiteSpeicher(":memory:") as speicher:
        assert Monitor(LeererAdapter(), speicher).einmal() is False
        gespeichert = speicher.lese(
            pd.Timestamp("2000-01-01", tz="UTC"),
            pd.Timestamp("2100-01-01", tz="UTC"),
        )

    assert gespeichert.empty
    assert "Keine Messwerte empfangen" in caplog.text


def test_monitor_cli_meldet_start_erfolg_und_stop(caplog, monkeypatch, tmp_path):
    """Der Einmalbetrieb protokolliert Start, erfolgreiche Abfrage und Stop."""
    monkeypatch.setattr("wpanalyse.adapters.luxtronik.LuxtronikAdapter", lambda _config: _adapter())
    monkeypatch.setattr(sys, "argv", ["monitor", "--db", str(tmp_path / "messwerte.sqlite"), "--einmal"])

    monitor.main()

    assert "Monitoring gestartet" in caplog.text
    assert "Messung gespeichert" in caplog.text
    assert "Monitoring beendet" in caplog.text
