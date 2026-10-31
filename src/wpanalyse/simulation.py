"""Erzeugt realistische Testdaten einer Luft-Wasser-Wärmepumpe – ohne echtes Gerät."""

import numpy as np
import pandas as pd


def simuliere(
    tage: int = 3,
    takten: bool = False,
    start: str = "2026-01-10",
    seed: int = 1,
    filter_verschmutzt: bool = False,
    heizstab_mild: bool = False,
    raum_kalt: bool = False,
    datenluecke: bool = False,
    stoerung: bool = False,
    heizkurve_zu_hoch: bool = False,
    abtauen: bool = False,
) -> pd.DataFrame:
    """Simuliert Minutenwerte.

    takten=True: Verdichter läuft in kurzen Zyklen (ca. 6 min an / 9 min aus) statt in langen.
    Die weiteren Parameter aktivieren jeweils ein synthetisches Fehlerszenario.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=tage * 24 * 60, freq="1min", tz="UTC")
    minute = np.arange(len(index))
    stunde = (minute / 60) % 24

    aussen_c = 0 + 4 * np.sin((stunde - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.3, len(index))

    # Ein/Aus-Zyklen des Verdichters
    if takten:
        an_min, aus_min = 6, 9
    else:
        an_min, aus_min = 180, 60  # ca. 6 Starts/Tag
    zyklus = an_min + aus_min
    verdichter_an = (minute % zyklus) < an_min

    vorlauf_soll = 35 - 0.5 * aussen_c + (5 if heizkurve_zu_hoch else 0)
    vorlauf_c = np.where(verdichter_an, vorlauf_soll, vorlauf_soll - 6) + rng.normal(0, 0.2, len(index))
    spreizung_k = 5 + 3 * minute / max(len(index) - 1, 1) if filter_verschmutzt else 5
    ruecklauf_c = np.where(verdichter_an, vorlauf_c - spreizung_k, vorlauf_c - 1)
    ruecklauf_c += rng.normal(0, 0.2, len(index))

    verdichter_leistung_w = np.where(verdichter_an, 1400 + 25 * (5 - aussen_c), 15.0)
    heizstab_an = heizstab_mild & (aussen_c > -5)
    leistung_w = verdichter_leistung_w + np.where(heizstab_an, 3000, 0)
    cop = np.clip(3.6 + 0.08 * aussen_c, 1.8, 5.5)
    waerme_w = np.where(verdichter_an, verdichter_leistung_w * cop, 0.0) + np.where(heizstab_an, 3000, 0)
    abtauen_aktiv = abtauen & (aussen_c >= 0) & (aussen_c <= 7) & ((minute % 180) < 8)
    waerme_w = np.where(abtauen_aktiv, 0.0, waerme_w)

    df = pd.DataFrame(
        {
            "aussen_c": aussen_c,
            "vorlauf_c": vorlauf_c,
            "ruecklauf_c": ruecklauf_c,
            "verdichter_an": verdichter_an,
            "leistung_w": leistung_w,
            "waerme_w": waerme_w,
            "heizstab_an": heizstab_an,
            "raum_wohnzimmer_c": (17.0 if raum_kalt else 20.8) + rng.normal(0, 0.15, len(index)),
            "raum_schlafzimmer_c": 18.4 + rng.normal(0, 0.15, len(index)),
        },
        index=index,
    )
    if stoerung:
        df["stoerung"] = None
        df.iloc[len(df) // 2, df.columns.get_loc("stoerung")] = "E101"
    if abtauen:
        df["betriebsart"] = np.where(abtauen_aktiv, "abtauen", "heizen")
    if datenluecke:
        mitte = len(df) // 2
        df = df.drop(index=df.index[mitte : mitte + min(60, len(df) - mitte)])
    return df
