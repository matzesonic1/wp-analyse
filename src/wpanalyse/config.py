"""Alle Schwellwerte zentral. Nach einigen Wochen Messung an das eigene Haus anpassen."""

from dataclasses import dataclass, field


@dataclass
class Config:
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
    raum_abgleich_differenz_k: float = 1.5

    # Datenqualität (A7)
    max_datenluecke_min: int = 30
