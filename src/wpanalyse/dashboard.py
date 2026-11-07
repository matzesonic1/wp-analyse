"""Streamlit-Dashboard für Wärmepumpen-Messwerte."""

import pandas as pd

from wpanalyse.analyse.verdichter import bewerte_verdichter
from wpanalyse.config import LuxtronikConfig, VerdichterConfig
from wpanalyse.logging_config import dashboard_logging_einstellungen, setze_dashboard_logging
from wpanalyse.simulation import simuliere
from wpanalyse.speicher.sqlite import SQLiteSpeicher

_LOGGING_AKTIV_SCHLUESSEL = "anwendungslogs_aktiv"
_LOGGING_STUFE_SCHLUESSEL = "anwendungslogs_stufe"


def berechne_starts_pro_tag(df: pd.DataFrame) -> pd.Series:
    """Zählt Verdichterstarts je UTC-Kalendertag.

    Liefert der Regler einen Start-Zähler (``verdichter_starts_zaehler``), wird dessen
    Zuwachs verwendet; das ist bei 60-s-Abfragen genauer als der An/Aus-Zustand.
    """
    if "verdichter_starts_zaehler" in df and df["verdichter_starts_zaehler"].notna().sum() > 1:
        zuwachs = pd.to_numeric(df["verdichter_starts_zaehler"]).diff().clip(lower=0).fillna(0)
        return zuwachs.groupby(zuwachs.index.normalize()).sum().astype(int).rename("starts_pro_tag")
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


DB_PFAD = "data/wp.sqlite"


def lade_live_daten(speicher: SQLiteSpeicher, stunden: int) -> pd.DataFrame:
    """Liest die letzten ``stunden`` Stunden aus der Datenbank."""
    bis = pd.Timestamp.now(tz="UTC") + pd.Timedelta(minutes=1)
    return speicher.lese(bis - pd.Timedelta(hours=stunden, minutes=1), bis)


def frage_regler_ab(speicher: SQLiteSpeicher, host: str, port: int, intervall_s: float) -> str:
    """Fragt den Regler ab, wenn die letzte Messung älter als das Intervall ist.

    Mehrere offene Browser-Tabs lösen so keine doppelten Abfragen aus.
    Liefert eine Statusmeldung für die Anzeige.
    """
    from wpanalyse.adapters.luxtronik import LuxtronikAdapter
    from wpanalyse.monitor import Monitor

    jetzt = pd.Timestamp.now(tz="UTC")
    letzte = lade_live_daten(speicher, 1)
    if not letzte.empty and (jetzt - letzte.index[-1]).total_seconds() < intervall_s - 5:
        return f"Letzte Messung {letzte.index[-1].tz_convert('Europe/Berlin'):%H:%M:%S}"
    adapter = LuxtronikAdapter(LuxtronikConfig(host=host, port=port))
    ok = Monitor(adapter, speicher, intervall_s).einmal()
    return "Abfrage erfolgreich" if ok else "Abfrage fehlgeschlagen (Regler erreichbar?)"


def zeige_aktuelle_werte(st, df: pd.DataFrame) -> None:
    """Zeigt die jüngste Messung als Kennzahlen, soweit die Spalten vorhanden sind."""
    letzte = df.iloc[-1]

    def wert(spalte: str):
        """Liefert den letzten Wert einer Spalte oder None, wenn sie fehlt oder leer ist."""
        if spalte not in df or pd.isna(letzte[spalte]):
            return None
        return letzte[spalte]

    kacheln = [
        ("Betriebsart", wert("betriebsart"), "{}"),
        (
            "Verdichter",
            None if wert("verdichter_an") is None else ("an" if wert("verdichter_an") else "aus"),
            "{}",
        ),
        ("Heizstab", None if wert("heizstab_an") is None else ("an" if wert("heizstab_an") else "aus"), "{}"),
        ("Verdichterstarts gesamt", wert("verdichter_starts_zaehler"), "{:,.0f}"),
        (
            "Verdichter-Betriebsstunden",
            None if wert("verdichter_betriebszeit_s") is None else wert("verdichter_betriebszeit_s") / 3600,
            "{:,.0f} h",
        ),
        (
            "Aktuelle Laufzeit",
            None if wert("verdichter_laufzeit_s") is None else wert("verdichter_laufzeit_s") / 60,
            "{:.0f} min",
        ),
        ("Heizleistung", wert("waerme_w"), "{:,.0f} W"),
        ("Außen", wert("aussen_c"), "{:.1f} °C"),
        ("Vorlauf", wert("vorlauf_c"), "{:.1f} °C"),
        ("Rücklauf", wert("ruecklauf_c"), "{:.1f} °C"),
        ("Rücklauf-Soll", wert("ruecklauf_soll_c"), "{:.1f} °C"),
        (
            "Spreizung",
            None
            if wert("vorlauf_c") is None or wert("ruecklauf_c") is None
            else wert("vorlauf_c") - wert("ruecklauf_c"),
            "{:.1f} K",
        ),
        ("Warmwasser", wert("warmwasser_c"), "{:.1f} °C"),
        ("Heißgas", wert("heissgas_c"), "{:.1f} °C"),
        ("Quelle ein", wert("quelle_ein_c"), "{:.1f} °C"),
        ("Heizstab 1 Laufzeit", wert("heizstab1_laufzeit_s"), "{:.0f} s"),
        ("Heizstab 2 Laufzeit", wert("heizstab2_laufzeit_s"), "{:.0f} s"),
        ("Abtauzeit", wert("abtauung_zeit_s"), "{:.0f} s"),
    ]
    kacheln = [k for k in kacheln if k[1] is not None]
    st.subheader(f"Aktuelle Werte ({df.index[-1].tz_convert('Europe/Berlin'):%d.%m. %H:%M:%S})")
    for beginn in range(0, len(kacheln), 6):
        spalten = st.columns(6)
        for spalte, (name, inhalt, format_) in zip(spalten, kacheln[beginn : beginn + 6], strict=False):
            spalte.metric(name, format_.format(inhalt))


def numerische_spalten(df: pd.DataFrame) -> list[str]:
    """Liefert alle Spalten, die Zahlen oder Wahrheitswerte mit mindestens einem Wert enthalten."""
    ergebnis = []
    for spalte in df.columns:
        werte = pd.to_numeric(df[spalte], errors="coerce")
        if werte.notna().any():
            ergebnis.append(spalte)
    return ergebnis


def bereite_auswahl_vor(df: pd.DataFrame, spalten: list[str]) -> pd.DataFrame:
    """Wandelt die gewählten Spalten für die Diagrammanzeige in Zahlen um (bool wird 0/1)."""
    return df[spalten].apply(
        lambda s: pd.to_numeric(s.map(lambda x: float(x) if isinstance(x, bool) else x), errors="coerce")
    )


def zeige_freie_auswahl(st, df: pd.DataFrame) -> None:
    """Zeigt beliebige Messwerte im Verlauf, Min/Max/Mittel und je Wert ein eigenes Diagramm."""
    st.subheader("Freie Auswahl – alle Messwerte")
    verfuegbar = numerische_spalten(df)
    vorgabe = [s for s in ("vorlauf_c", "ruecklauf_c") if s in verfuegbar]
    auswahl = st.multiselect("Werte wählen", verfuegbar, default=vorgabe, key="freie_auswahl")
    if not auswahl:
        st.info("Wähle mindestens einen Wert.")
        return
    daten = bereite_auswahl_vor(df, auswahl)
    st.line_chart(daten)
    st.dataframe(daten.describe().loc[["min", "mean", "max"]].T.rename(columns={"mean": "mittel"}))
    if st.checkbox("Je Wert ein eigenes Diagramm", key="einzeldiagramme"):
        for spalte in auswahl:
            st.caption(spalte)
            st.line_chart(daten[[spalte]])


def zeige_verdichter_bewertung(st, df: pd.DataFrame) -> None:
    """Zeigt Anläufe im Verhältnis zur Betriebszeit und die Plausibilität zum Verdichtertausch."""
    if not {"verdichter_starts_zaehler", "verdichter_betriebszeit_s"} <= set(df.columns):
        return
    letzte = df[["verdichter_starts_zaehler", "verdichter_betriebszeit_s"]].dropna()
    if letzte.empty:
        return
    ergebnis = bewerte_verdichter(
        int(letzte["verdichter_starts_zaehler"].iloc[-1]),
        float(letzte["verdichter_betriebszeit_s"].iloc[-1]),
        pd.Timestamp.now(tz="UTC"),
        VerdichterConfig(),
        df,
    )
    st.subheader("Verdichter: Anläufe zu Betriebszeit")
    spalten = st.columns(4)
    spalten[0].metric("Starts (Zähler)", f"{ergebnis.starts:,.0f}")
    spalten[1].metric("Betriebszeit", f"{ergebnis.betriebszeit_h:,.0f} h")
    if ergebnis.mittlere_laufzeit_min is not None:
        spalten[2].metric("Mittlere Laufzeit je Start", f"{ergebnis.mittlere_laufzeit_min:.0f} min")
    if ergebnis.max_starts_pro_stunde is not None:
        spalten[3].metric("Max. Starts/h im Zeitraum", ergebnis.max_starts_pro_stunde)
    for hinweis in ergebnis.hinweise:
        st.warning(hinweis)
    if not ergebnis.hinweise:
        st.success("Anläufe und Betriebszeit passen zusammen.")


def zeige_diagramme(st, df: pd.DataFrame) -> None:
    """Zeichnet alle Dashboard-Diagramme für die vorhandenen Spalten."""
    if df.empty:
        return
    zeige_aktuelle_werte(st, df)
    zeige_verdichter_bewertung(st, df)

    st.subheader("Temperaturen")
    spalten = [s for s in ("vorlauf_c", "ruecklauf_c", "aussen_c", "warmwasser_c") if s in df]
    st.line_chart(df[spalten])

    zusatz = [
        s for s in ("ruecklauf_soll_c", "heissgas_c", "quelle_ein_c") if s in df and df[s].notna().any()
    ]
    if zusatz:
        st.subheader("Weitere Temperaturen")
        st.line_chart(df[zusatz])

    st.subheader("Leistung")
    leistung = [s for s in ("leistung_w", "waerme_w") if s in df and df[s].notna().any()]
    if leistung:
        st.line_chart(df[leistung])
    else:
        st.info("Keine Leistungswerte vorhanden.")

    st.subheader("Verdichterstarts pro Tag")
    st.bar_chart(berechne_starts_pro_tag(df))

    if "verdichter_starts_zaehler" in df and df["verdichter_starts_zaehler"].notna().any():
        st.subheader("Verdichterstarts gesamt (Zählerstand)")
        st.line_chart(df[["verdichter_starts_zaehler"]])

    laufzeiten = [
        s
        for s in ("verdichter_laufzeit_s", "heizstab1_laufzeit_s", "heizstab2_laufzeit_s", "abtauung_zeit_s")
        if s in df and df[s].notna().any()
    ]
    if laufzeiten:
        st.subheader("Laufzeiten (Sekunden)")
        st.line_chart(df[laufzeiten])

    if "betriebsart" in df and df["betriebsart"].notna().any():
        st.subheader("Betriebsart (Anteil der Messungen)")
        st.bar_chart(df["betriebsart"].value_counts())

    st.subheader("Arbeitszahl nach Außentemperatur")
    az_nach_aussen = berechne_az_nach_aussentemperatur(df)
    if az_nach_aussen.empty:
        st.info("Für den AZ-Vergleich fehlen Wärme-, Strom- oder Außentemperaturwerte.")
    else:
        st.scatter_chart(az_nach_aussen, x="aussen_c", y="az")

    zeige_freie_auswahl(st, df)

    with st.expander("Alle Messwerte (Tabelle)"):
        st.dataframe(df.sort_index(ascending=False).astype(str))


def _aendere_logging(st, einstellung: str) -> None:
    if einstellung == "aktiv":
        setze_dashboard_logging(aktiviert=st.session_state[_LOGGING_AKTIV_SCHLUESSEL])
    else:
        setze_dashboard_logging(stufe=st.session_state[_LOGGING_STUFE_SCHLUESSEL])


def _zeige_logging_steuerung(st) -> None:
    """Zeigt und synchronisiert die prozessweiten Logging-Einstellungen."""
    aktiviert, stufe = dashboard_logging_einstellungen()
    st.session_state[_LOGGING_AKTIV_SCHLUESSEL] = aktiviert
    st.session_state[_LOGGING_STUFE_SCHLUESSEL] = stufe
    st.sidebar.checkbox(
        "Anwendungslogs",
        key=_LOGGING_AKTIV_SCHLUESSEL,
        on_change=_aendere_logging,
        args=(st, "aktiv"),
    )
    st.sidebar.selectbox(
        "Logstufe",
        ("DEBUG", "INFO", "WARNING", "ERROR"),
        key=_LOGGING_STUFE_SCHLUESSEL,
        disabled=not aktiviert,
        on_change=_aendere_logging,
        args=(st, "stufe"),
    )


def main() -> None:
    """Startet das Dashboard mit Simulation oder Live-Betrieb (Abfrage alle 60 s)."""
    import streamlit as st

    st.set_page_config(page_title="WP-Analyse", layout="wide")
    st.title("Wärmepumpen-Dashboard")

    _zeige_logging_steuerung(st)
    quelle = st.sidebar.radio("Datenquelle", ["Live-Betrieb", "Simulation"])
    if quelle == "Simulation":
        st.caption("Simulierte Messdaten.")
        zeige_diagramme(st, simuliere(tage=3))
        return

    vorgabe = LuxtronikConfig.aus_umgebung()
    host = st.sidebar.text_input("Luxtronik-Host", vorgabe.host or "192.168.178.116")
    port = st.sidebar.number_input("Luxtronik-Port", min_value=1, max_value=65535, value=vorgabe.port, step=1)
    stunden = st.sidebar.slider("Zeitraum (Stunden)", 1, 72, 6)
    intervall_s = vorgabe.abfrage_intervall_s

    @st.fragment(run_every=intervall_s)
    def live() -> None:
        with SQLiteSpeicher(DB_PFAD) as speicher:
            status = frage_regler_ab(speicher, host, int(port), intervall_s)
            df = lade_live_daten(speicher, stunden)
        st.caption(f"Live-Betrieb, Abfrage alle {intervall_s:.0f} s (nur lesend). {status}")
        if df.empty:
            st.info("Noch keine Messwerte vorhanden.")
            return
        zeige_diagramme(st, df)

    live()


if __name__ == "__main__":
    main()
