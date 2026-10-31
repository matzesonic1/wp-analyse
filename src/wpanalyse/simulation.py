"""Erzeugt realistische Testdaten einer Luft-Wasser-Wärmepumpe – ohne echtes Gerät.

Grundversion: Normalbetrieb und Szenario 'takten'. Weitere Szenarien siehe docs/backlog.md (Issue 5).
"""

import numpy as np
import pandas as pd


def simuliere(tage: int = 3, takten: bool = False, start: str = "2026-01-10", seed: int = 1) -> pd.DataFrame:
    """Simuliert Minutenwerte.

    takten=True: Verdichter läuft in kurzen Zyklen (ca. 6 min an / 9 min aus) statt in langen.
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

    vorlauf_soll = 35 - 0.5 * aussen_c  # einfache Heizkurve
    vorlauf_c = np.where(verdichter_an, vorlauf_soll, vorlauf_soll - 6) + rng.normal(0, 0.2, len(index))
    ruecklauf_c = np.where(verdichter_an, vorlauf_c - 5, vorlauf_c - 1) + rng.normal(0, 0.2, len(index))

    leistung_w = np.where(verdichter_an, 1400 + 25 * (5 - aussen_c), 15.0)
    cop = np.clip(3.6 + 0.08 * aussen_c, 1.8, 5.5)
    waerme_w = np.where(verdichter_an, leistung_w * cop, 0.0)

    df = pd.DataFrame(
        {
            "aussen_c": aussen_c,
            "vorlauf_c": vorlauf_c,
            "ruecklauf_c": ruecklauf_c,
            "verdichter_an": verdichter_an,
            "leistung_w": leistung_w,
            "waerme_w": waerme_w,
            "heizstab_an": False,
            "raum_wohnzimmer_c": 20.8 + rng.normal(0, 0.15, len(index)),
            "raum_schlafzimmer_c": 18.4 + rng.normal(0, 0.15, len(index)),
        },
        index=index,
    )
    return df
