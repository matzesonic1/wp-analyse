"""Bewertet die Temperaturdifferenz zwischen Vorlauf und Rücklauf (Regel A3)."""

from dataclasses import dataclass, field

import pandas as pd

from ..config import Config
from ..models import Befund, Bewertung


@dataclass
class SpreizungErgebnis:
    """Mittlere Spreizung sowie Bewertung und gegebenenfalls Befunde."""

    mittlere_spreizung_k: float
    bewertung: Bewertung
    befunde: list[Befund] = field(default_factory=list)


def analysiere_spreizung(df: pd.DataFrame, cfg: Config) -> SpreizungErgebnis:
    """Berechnet die Spreizung während des Verdichterbetriebs und prüft A3.

    Für den langfristigen Vergleich werden das 7-Tage-Mittel und das
    30-Tage-Mittel der verfügbaren Messreihe herangezogen.
    """
    spreizung = (df["vorlauf_c"] - df["ruecklauf_c"])[
        df["verdichter_an"].fillna(False).astype(bool)
    ].dropna()
    mittlere_spreizung = float(spreizung.mean()) if not spreizung.empty else 0.0
    befunde: list[Befund] = []

    if not spreizung.empty:
        ende = spreizung.index.max()
        start = spreizung.index.min()
        if ende - start >= pd.Timedelta(days=30):
            spreizung_7_tage = spreizung[spreizung.index >= ende - pd.Timedelta(days=7)]
            spreizung_30_tage = spreizung[spreizung.index >= ende - pd.Timedelta(days=30)]
            mittel_7_tage = spreizung_7_tage.mean()
            mittel_30_tage = spreizung_30_tage.mean()

            if (
                not spreizung_7_tage.empty
                and mittel_30_tage > 0
                and mittel_7_tage > mittel_30_tage * (1 + cfg.spreizung_anstieg_prozent / 100)
            ):
                anstieg_prozent = (mittel_7_tage / mittel_30_tage - 1) * 100
                befunde.append(Befund(
                    "A3",
                    Bewertung.HINWEIS,
                    f"Die Spreizung der letzten 7 Tage liegt mit {mittel_7_tage:.1f} K "
                    f"{anstieg_prozent:.0f} % über dem 30-Tage-Mittel von {mittel_30_tage:.1f} K. "
                    "Prüfe Filter oder Schmutzfänger auf Verschmutzung.",
                ))

    bewertung = Bewertung.HINWEIS if befunde else Bewertung.OK
    return SpreizungErgebnis(round(mittlere_spreizung, 1), bewertung, befunde)
