import pandas as pd

from wpanalyse.dashboard import berechne_az_nach_aussentemperatur, berechne_starts_pro_tag
from wpanalyse.simulation import simuliere


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
