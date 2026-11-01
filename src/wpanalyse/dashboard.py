"""Streamlit-Dashboard für Wärmepumpen-Messwerte."""

import pandas as pd

from wpanalyse.simulation import simuliere


def berechne_starts_pro_tag(df: pd.DataFrame) -> pd.Series:
    """Zählt Verdichterstarts je UTC-Kalendertag."""
    if "verdichter_an" not in df:
        return pd.Series(dtype="int64", name="starts_pro_tag")

    verdichter_an = df["verdichter_an"].fillna(False).astype(bool)
    starts = verdichter_an & ~verdichter_an.shift(1, fill_value=False)
    return starts.groupby(starts.index.normalize()).sum().astype(int).rename("starts_pro_tag")


def berechne_az_nach_aussentemperatur(df: pd.DataFrame) -> pd.DataFrame:
    """Berechnet die Tages-AZ und ordnet sie der mittleren Außentemperatur zu."""
    spalten = {"aussen_c", "leistung_w", "waerme_w"}
    if not spalten.issubset(df.columns):
        return pd.DataFrame(columns=["aussen_c", "az"])

    tageswerte = df.groupby(df.index.normalize())
    energie = tageswerte[["waerme_w", "leistung_w"]].sum(min_count=1)
    strom_w = energie["leistung_w"].where(energie["leistung_w"] > 0)
    az = (energie["waerme_w"] / strom_w).rename("az")
    aussen_c = tageswerte["aussen_c"].mean().rename("aussen_c")
    return pd.concat([aussen_c, az], axis=1).dropna(subset=["aussen_c", "az"])


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="WP-Analyse", layout="wide")
    st.title("Wärmepumpen-Dashboard")
    st.caption("Aktuell mit simulierten Messdaten.")

    df = simuliere(tage=3)
    st.subheader("Temperaturen")
    st.line_chart(df[["vorlauf_c", "ruecklauf_c", "aussen_c"]])

    st.subheader("Elektrische Leistung")
    st.line_chart(df[["leistung_w"]])

    st.subheader("Verdichterstarts pro Tag")
    st.bar_chart(berechne_starts_pro_tag(df))

    st.subheader("Arbeitszahl nach Außentemperatur")
    az_nach_aussen = berechne_az_nach_aussentemperatur(df)
    if az_nach_aussen.empty:
        st.info("Für den AZ-Vergleich fehlen Wärme-, Strom- oder Außentemperaturwerte.")
    else:
        st.scatter_chart(az_nach_aussen, x="aussen_c", y="az")


if __name__ == "__main__":
    main()
