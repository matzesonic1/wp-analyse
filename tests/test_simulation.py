import numpy as np

from wpanalyse.simulation import simuliere


def test_normalbetrieb_ohne_fehlerszenarien():
    df = simuliere(tage=1)

    assert len(df) == 24 * 60
    assert (df.index.to_series().diff().dropna() == np.timedelta64(1, "m")).all()
    assert not df["heizstab_an"].any()
    assert "stoerung" not in df
    assert "betriebsart" not in df
    assert df["raum_wohnzimmer_c"].mean() > 20


def test_filter_verschmutzt_erhoeht_die_spreizung():
    df = simuliere(tage=3, filter_verschmutzt=True)
    spreizung_k = (df["vorlauf_c"] - df["ruecklauf_c"])[df["verdichter_an"]]

    assert spreizung_k.iloc[-10:].mean() - spreizung_k.iloc[:10].mean() > 2


def test_heizstab_szenario_ist_bei_milden_temperaturen_sichtbar():
    df = simuliere(tage=1, heizstab_mild=True)

    assert (df["heizstab_an"] & (df["aussen_c"] > -5)).any()


def test_kalter_raum_ist_sichtbar():
    df = simuliere(tage=1, raum_kalt=True)

    assert df["raum_wohnzimmer_c"].mean() < 18


def test_datenluecke_fehlende_zeitstempel():
    df = simuliere(tage=1, datenluecke=True)
    abstaende = df.index.to_series().diff().dropna()

    assert len(df) == 24 * 60 - 60
    assert abstaende.max() == np.timedelta64(61, "m")


def test_stoerung_ist_mit_fehlercode_sichtbar():
    df = simuliere(tage=1, stoerung=True)

    assert df["stoerung"].dropna().tolist() == ["E101"]


def test_zu_hohe_heizkurve_erhoeht_den_vorlauf():
    normal = simuliere(tage=1)
    zu_hoch = simuliere(tage=1, heizkurve_zu_hoch=True)

    assert (zu_hoch["vorlauf_c"] - normal["vorlauf_c"]).mean() > 4.5


def test_abtauung_ist_in_der_betriebsart_sichtbar():
    df = simuliere(tage=3, abtauen=True)

    assert (df["betriebsart"] == "abtauen").any()
