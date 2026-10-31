from datetime import UTC, datetime

import pandas as pd

from wpanalyse.speicher import SQLiteSpeicher


def test_speichert_und_laesst_zeitraum_mit_utc_index(tmp_path):
    pfad = tmp_path / "messwerte.sqlite"
    zeit = pd.date_range("2026-01-01", periods=3, freq="min", tz="UTC")
    df = pd.DataFrame(
        {"vorlauf_c": [32.5, None, 34.0], "verdichter_an": [True, False, True]},
        index=zeit,
    )

    with SQLiteSpeicher(pfad) as speicher:
        speicher.speichern(df)
    with SQLiteSpeicher(pfad) as speicher:
        ergebnis = speicher.lese(
            datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
        )

    assert ergebnis.index.equals(zeit[1:3])
    assert ergebnis.index.tz == UTC
    assert ergebnis["vorlauf_c"].iloc[0] != ergebnis["vorlauf_c"].iloc[0]
    assert ergebnis["verdichter_an"].tolist() == [False, True]


def test_speichern_aktualisiert_doppelten_zeitstempel(tmp_path):
    with SQLiteSpeicher(tmp_path / "messwerte.sqlite") as speicher:
        zeit = pd.date_range("2026-01-01", periods=1, tz="UTC")
        speicher.speichern(pd.DataFrame({"vorlauf_c": [30.0]}, index=zeit))
        speicher.speichern(pd.DataFrame({"vorlauf_c": [31.0]}, index=zeit))

        ergebnis = speicher.lese(zeit[0], zeit[0] + pd.Timedelta(minutes=1))

    assert ergebnis["vorlauf_c"].tolist() == [31.0]


def test_laden_leerer_zeitraum_bewahrt_spalten_und_utc_index(tmp_path):
    with SQLiteSpeicher(tmp_path / "messwerte.sqlite") as speicher:
        speicher.speichern(pd.DataFrame(columns=["vorlauf_c"], index=pd.DatetimeIndex([], tz="UTC")))

        ergebnis = speicher.lese(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )

    assert ergebnis.empty
    assert list(ergebnis.columns) == ["vorlauf_c"]
    assert ergebnis.index.tz == UTC
