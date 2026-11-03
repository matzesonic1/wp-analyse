"""Zentrale, objektspezifisch anpassbare Schwellwerte für die Analysen."""

from dataclasses import dataclass, field


@dataclass
class Config:
    """Enthält Grenzwerte und Sollwerte für Analysen und Berichte.

    Die Standardwerte dienen als Startpunkt und sollten an das jeweilige Gebäude
    und die dort installierte Wärmepumpe angepasst werden.
    """

    # Taktung (Regel A1)
    max_starts_pro_tag: int = 20
    hinweis_starts_pro_tag: int = 10
    min_zykluslaufzeit_min: float = 10.0
    ziel_zykluslaufzeit_min: float = 30.0

    # Spreizung (Regel A3)
    spreizung_soll_min_k: float = 3.0
    spreizung_soll_max_k: float = 7.0
    spreizung_anstieg_prozent: float = 30.0

    # Effizienz (A2) und Heizstab (A4)
    az_abweichung_prozent: float = 20.0
    az_erwartung_bei_minus_10_c: float = 2.3
    az_erwartung_pro_c: float = 0.1
    heizstab_max_aussen_c: float = -5.0

    # Komfort (A5, A6)
    raum_soll_c: dict[str, float] = field(
        default_factory=lambda: {"wohnzimmer": 20.5, "bad": 22.0, "schlafzimmer": 18.0}
    )
    raum_anteil_toleranz_k: float = 1.0
    raum_toleranz_k: float = 1.5
    raum_unter_soll_max_stunden: float = 2.0
    raum_kritisch_c: float = 17.0
    raum_warnung_dauer_std: float = 2.0
    raum_abgleich_differenz_k: float = 1.5

    # Datenqualität (A7)
    max_datenluecke_min: int = 30


# Zuordnung Projektfeld -> Luxtronik-Calculation (nur lesend abgefragt)
LUXTRONIK_FELDER: dict[str, str] = {
    "aussen_c": "ID_WEB_Temperatur_TA",
    "vorlauf_c": "ID_WEB_Temperatur_TVL",
    "ruecklauf_c": "ID_WEB_Temperatur_TRL",
    "ruecklauf_soll_c": "ID_WEB_Sollwert_TRL_HZ",
    "warmwasser_c": "ID_WEB_Temperatur_TBW",
    "heissgas_c": "ID_WEB_Temperatur_THG",
    "quelle_ein_c": "ID_WEB_Temperatur_TWE",
    "quelle_aus_c": "ID_WEB_Temperatur_TWA",
    "waerme_w": "Heat_Output",
    "verdichter_laufzeit_s": "ID_WEB_Time_WPein_akt",
    "verdichter_starts_zaehler": "ID_WEB_Zaehler_BetrZeitImpVD1",
    "verdichter_betriebszeit_s": "ID_WEB_Zaehler_BetrZeitVD1",
    "heizstab1_laufzeit_s": "ID_WEB_Time_ZWE1_akt",
    "heizstab2_laufzeit_s": "ID_WEB_Time_ZWE2_akt",
    "abtauung_zeit_s": "ID_WEB_Time_AbtIn",
    "betriebsart_roh": "ID_WEB_WP_BZ_akt",
}


@dataclass
class LuxtronikConfig:
    """Verbindungs- und Abfrageeinstellungen für den Luxtronik-Regler.

    Der Host wird aus der Umgebungsvariable ``LUXTRONIK_HOST`` gelesen, damit keine
    Adressen im Code stehen.
    """

    host: str = ""
    port: int = 8889
    abfrage_intervall_s: float = 60.0
    min_intervall_s: float = 60.0
    # Zuordnung roher Betriebsart-Texte des Reglers zu Projekt-Betriebsarten
    betriebsart_zuordnung: dict[str, str] = field(
        default_factory=lambda: {
            "heating": "heizen",
            "hot water": "warmwasser",
            "defrost": "abtauen",
            "no request": "aus",
            "cooling": "kuehlen",
        }
    )

    @classmethod
    def aus_umgebung(cls) -> "LuxtronikConfig":
        """Erzeugt die Konfiguration aus ``LUXTRONIK_HOST`` und ``LUXTRONIK_PORT``."""
        import os

        return cls(
            host=os.environ.get("LUXTRONIK_HOST", ""),
            port=int(os.environ.get("LUXTRONIK_PORT", "8889")),
        )
