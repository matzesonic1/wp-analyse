"""Berechnet die temperaturabhängige Arbeitszahl und prüft den Heizstabeinsatz."""

from dataclasses import dataclass, field

import pandas as pd

from ..config import Config
from ..models import Befund, Bewertung


@dataclass
class EffizienzErgebnis:
    """Tagesarbeitszahlen, Gesamtbewertung und zugehörige Befunde."""

    tages_az: dict[str, float]
    bewertung: Bewertung
    befunde: list[Befund] = field(default_factory=list)


def analysiere_effizienz(df: pd.DataFrame, cfg: Config) -> EffizienzErgebnis:
    """Bewertet Tagesarbeitszahlen und Heizstabmesswerte.

    Die Arbeitszahl wird aus Wärme- und Stromenergie je Kalendertag berechnet.
    Die Bewertung der Arbeitszahl berücksichtigt die mittlere Außentemperatur
    des jeweiligen Tages.
    """
    befunde: list[Befund] = []
    tages_az: dict[str, float] = {}

    if "waerme_kwh" not in df or "strom_kwh" not in df:
        befunde.append(Befund(
            "A2",
            Bewertung.HINWEIS,
            "AZ nicht berechenbar: Wärme- und Stromenergie (waerme_kwh, strom_kwh) werden benötigt.",
        ))
    else:
        for tag, tagesdaten in df.groupby(df.index.date):
            waerme_kwh = tagesdaten["waerme_kwh"].sum(min_count=1)
            strom_kwh = tagesdaten["strom_kwh"].sum(min_count=1)
            if pd.isna(waerme_kwh) or pd.isna(strom_kwh) or strom_kwh <= 0:
                continue

            az = float(waerme_kwh / strom_kwh)
            tag_text = tag.isoformat()
            tages_az[tag_text] = round(az, 2)
            if "aussen_c" not in tagesdaten:
                continue
            aussen_c = tagesdaten["aussen_c"].mean()
            if pd.isna(aussen_c):
                continue

            erwartete_az = cfg.az_erwartung_bei_minus_10_c + (
                aussen_c + 10
            ) * cfg.az_erwartung_pro_c
            grenzwert_az = erwartete_az * (1 - cfg.az_abweichung_prozent / 100)
            if az < grenzwert_az:
                befunde.append(Befund(
                    "A2",
                    Bewertung.WARNUNG,
                    f"Die Tages-AZ am {tag_text} beträgt {az:.2f}; bei durchschnittlich "
                    f"{aussen_c:.1f} °C wären etwa {erwartete_az:.2f} zu erwarten. "
                    "Die Abweichung liegt über dem Grenzwert – Effizienz prüfen.",
                ))

    if "heizstab_an" in df and "aussen_c" in df:
        heizstab_mild = df["heizstab_an"].fillna(False).astype(bool) & (
            df["aussen_c"] > cfg.heizstab_max_aussen_c
        )
        if heizstab_mild.any():
            max_aussen_c = df.loc[heizstab_mild, "aussen_c"].max()
            befunde.append(Befund(
                "A4",
                Bewertung.WARNUNG,
                f"Der Heizstab war bei bis zu {max_aussen_c:.1f} °C Außentemperatur aktiv. "
                f"Er sollte erst unter {cfg.heizstab_max_aussen_c:.1f} °C oder bei einer "
                "Legionellenschaltung laufen.",
            ))

    bewertung = max(
        (befund.bewertung for befund in befunde),
        key=lambda wert: list(Bewertung).index(wert),
        default=Bewertung.OK,
    )
    return EffizienzErgebnis(tages_az, bewertung, befunde)
