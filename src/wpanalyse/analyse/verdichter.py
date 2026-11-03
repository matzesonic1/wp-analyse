"""Bewertung der Verdichter-Zähler: Anläufe im Verhältnis zur Betriebszeit (reine Funktion)."""

from dataclasses import dataclass, field

import pandas as pd

from wpanalyse.config import VerdichterConfig


@dataclass
class VerdichterBewertung:
    """Ergebnis der Verdichter-Bewertung mit Kennzahlen und Hinweisen."""

    starts: int
    betriebszeit_h: float
    mittlere_laufzeit_min: float | None
    max_betriebszeit_seit_tausch_h: float
    zaehler_enthaelt_altwerte: bool
    max_starts_pro_stunde: int | None
    hinweise: list[str] = field(default_factory=list)


def starts_pro_stunde_max(df: pd.DataFrame) -> int | None:
    """Größte Zahl an Starts innerhalb eines gleitenden 60-Minuten-Fensters (aus dem Start-Zähler)."""
    if "verdichter_starts_zaehler" not in df:
        return None
    zaehler = pd.to_numeric(df["verdichter_starts_zaehler"], errors="coerce").dropna()
    if len(zaehler) < 2:
        return None
    zuwachs = zaehler.diff().clip(lower=0).fillna(0)
    return int(zuwachs.rolling("60min").sum().max())


def bewerte_verdichter(
    starts_gesamt: int,
    betriebszeit_s: float,
    jetzt: pd.Timestamp,
    cfg: VerdichterConfig,
    verlauf: pd.DataFrame | None = None,
) -> VerdichterBewertung:
    """Prüft, ob Anläufe und Betriebszeit zusammenpassen und ob der Zähler zum Tausch passt.

    Ist die Zählerbasis zum Tauschzeitpunkt bekannt, wird sie abgezogen. Andernfalls wird
    geprüft, ob die Betriebszeit seit dem frühesten Tauschtermin überhaupt möglich ist.
    """
    hinweise: list[str] = []
    starts = starts_gesamt - (cfg.basis_starts or 0)
    betrieb_s = betriebszeit_s - (cfg.basis_betriebszeit_s or 0)
    betrieb_h = betrieb_s / 3600

    seit = pd.Timestamp(cfg.tausch_fruehestens, tz="UTC")
    max_h = max(0.0, (jetzt - seit).total_seconds() / 3600)
    basis_bekannt = cfg.basis_starts is not None and cfg.basis_betriebszeit_s is not None
    altwerte = not basis_bekannt and betrieb_h > max_h
    if altwerte:
        hinweise.append(
            f"Betriebszeit {betrieb_h:,.0f} h ist größer als seit dem Tausch möglich ({max_h:,.0f} h): "
            "Die Zähler wurden beim Tausch nicht zurückgesetzt. Zählerstände vom Tauschtag als "
            "basis_starts/basis_betriebszeit_s eintragen."
        )

    mittel_min = betrieb_s / 60 / starts if starts > 0 else None
    # Mittelwerte über die Gesamtlaufzeit sind nur mit bekannter Basis dem neuen Verdichter zuzuordnen
    if mittel_min is not None and not altwerte:
        if mittel_min < cfg.min_mittlere_laufzeit_min:
            hinweise.append(f"Mittlere Laufzeit je Start {mittel_min:.0f} min unter {cfg.min_mittlere_laufzeit_min:.0f} min.")
        elif mittel_min < cfg.ziel_mittlere_laufzeit_min:
            hinweise.append(f"Mittlere Laufzeit je Start {mittel_min:.0f} min unter Ziel {cfg.ziel_mittlere_laufzeit_min:.0f} min.")

    spitze = starts_pro_stunde_max(verlauf) if verlauf is not None else None
    if spitze is not None:
        if spitze > cfg.max_starts_pro_stunde:
            hinweise.append(f"{spitze} Starts innerhalb einer Stunde (Grenze {cfg.max_starts_pro_stunde}).")
        elif spitze >= cfg.hinweis_starts_pro_stunde:
            hinweise.append(f"{spitze} Starts innerhalb einer Stunde (Hinweisgrenze {cfg.hinweis_starts_pro_stunde}).")

    return VerdichterBewertung(
        starts=starts,
        betriebszeit_h=betrieb_h,
        mittlere_laufzeit_min=mittel_min,
        max_betriebszeit_seit_tausch_h=max_h,
        zaehler_enthaelt_altwerte=altwerte,
        max_starts_pro_stunde=spitze,
        hinweise=hinweise,
    )
