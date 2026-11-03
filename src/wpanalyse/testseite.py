"""Streamlit-Testoberfläche für die manuelle, lesende Abfrage des Luxtronik-Reglers.

Start: ``python -m streamlit run src\\wpanalyse\testseite.py``
"""

import time

from wpanalyse.config import LUXTRONIK_FELDER, LuxtronikConfig


def main() -> None:
    """Zeigt die abgefragten Felder und löst auf Knopfdruck eine einzelne Abfrage aus."""
    import pandas as pd
    import streamlit as st

    from wpanalyse.adapters.luxtronik import LuxtronikAdapter
    from wpanalyse.speicher.sqlite import SQLiteSpeicher

    st.title("Luxtronik – Testabfrage (nur lesend)")
    vorgabe = LuxtronikConfig.aus_umgebung()
    host = st.text_input("Host", vorgabe.host or "192.168.178.116")
    port = st.number_input("Port", value=vorgabe.port, step=1)
    speichern = st.checkbox("Messung in data/wp.sqlite speichern", value=False)

    with st.expander("Abgefragte Felder"):
        st.table(
            pd.DataFrame({"Projektfeld": list(LUXTRONIK_FELDER), "Luxtronik-ID": list(LUXTRONIK_FELDER.values())})
        )

    # Sperre gegen zu häufiges Abfragen (Schonung des Reglers)
    config = LuxtronikConfig(host=host, port=int(port))
    letzte = st.session_state.get("letzte_abfrage", 0.0)
    warte_s = config.min_intervall_s - (time.monotonic() - letzte)
    if st.button("Jetzt einmal abfragen", disabled=warte_s > 0):
        try:
            df = LuxtronikAdapter(config).aktuell()
        except (OSError, ValueError, ImportError) as fehler:
            st.error(f"Abfrage fehlgeschlagen: {fehler}")
        else:
            st.session_state["letzte_abfrage"] = time.monotonic()
            st.success(f"Abfrage um {df.index[0].isoformat()} erfolgreich")
            st.dataframe(df.T.astype(str))
            if speichern:
                with SQLiteSpeicher("data/wp.sqlite") as speicher:
                    speicher.speichern(df)
                st.info("Gespeichert in data/wp.sqlite")
    if warte_s > 0:
        st.caption(f"Nächste Abfrage in {warte_s:.0f} s möglich (Mindestabstand 60 s).")


main()
