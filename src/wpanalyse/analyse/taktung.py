"""Taktungs-Analyse (Regel A1). Dient als MUSTER für weitere Analyse-Module."""

from dataclasses import dataclass, field

import pandas as pd

from ..config import Config
from ..models import Befund, Bewertung


@dataclass
class TaktungErgebnis:
    starts_pro_tag: float
    mittlere_laufzeit_min: float
    bewertung: Bewertung
    befunde: list[Befund] = field(default_factory=list)


def analysiere_taktung(df: pd.DataFrame, cfg: Config) -> TaktungErgebnis:
    """Zählt Verdichterstarts und misst die mittlere Laufzeit pro Zyklus."""
    an = df["verdichter_an"].fillna(False).astype(bool)
    starts = an & ~an.shift(1, fill_value=False)
    anzahl_starts = int(starts.sum())

    tage = max((df.index[-1] - df.index[0]).total_seconds() / 86400, 1 / 24)
    starts_pro_tag = anzahl_starts / tage

    # Laufzeit je Zyklus: Minuten 'an' je Zyklus-Nummer
    zyklus_nr = starts.cumsum()
    abtast_min = pd.Series(df.index).diff().median().total_seconds() / 60
    laufzeiten = an[an].groupby(zyklus_nr[an]).size() * abtast_min
    mittlere_laufzeit = float(laufzeiten.mean()) if len(laufzeiten) else 0.0

    befunde: list[Befund] = []
    if starts_pro_tag > cfg.max_starts_pro_tag or (len(laufzeiten) and mittlere_laufzeit < cfg.min_zykluslaufzeit_min):
        bewertung = Bewertung.WARNUNG
        befunde.append(Befund(
            "A1", bewertung,
            f"Der Verdichter startet {starts_pro_tag:.0f}× pro Tag und läuft im Mittel nur "
            f"{mittlere_laufzeit:.0f} min am Stück. Das verschleißt den Verdichter und kostet Effizienz. "
            "Mögliche Ursachen: Heizkurve zu hoch, zu wenig Wasservolumen, schließende Raumthermostate.",
        ))
    elif starts_pro_tag > cfg.hinweis_starts_pro_tag or mittlere_laufzeit < cfg.ziel_zykluslaufzeit_min:
        bewertung = Bewertung.HINWEIS
        befunde.append(Befund(
            "A1", bewertung,
            f"{starts_pro_tag:.0f} Starts pro Tag, mittlere Laufzeit {mittlere_laufzeit:.0f} min – noch ok, "
            "aber mit Luft nach oben.",
        ))
    else:
        bewertung = Bewertung.OK

    return TaktungErgebnis(round(starts_pro_tag, 1), round(mittlere_laufzeit, 1), bewertung, befunde)
