"""Bewertet Raumtemperaturen, Unterversorgung und kritische Kälte (A5 und A6)."""

from dataclasses import dataclass, field

import pandas as pd

from ..config import Config
from ..models import Befund, Bewertung


@dataclass
class KomfortErgebnis:
    """Komfortkennzahlen, kältester Raum, Gesamtbewertung und Befunde."""

    anteil_unter_soll: dict[str, float]
    kaeltester_raum: str | None
    kaelteste_mitteltemperatur_c: float | None
    bewertung: Bewertung
    befunde: list[Befund] = field(default_factory=list)


def analysiere_komfort(df: pd.DataFrame, cfg: Config) -> KomfortErgebnis:
    """Bewertet Raumtemperaturspalten anhand der konfigurierten Raum-Sollwerte.

    Zeitanteile und zusammenhängende Untertemperaturphasen berücksichtigen nur
    positive Messintervalle, die kürzer als die erlaubte Datenlücke sind.
    """
    raum_spalten = [
        spalte for spalte in df.columns
        if spalte.startswith("raum_") and spalte.endswith("_c") and spalte[5:-2]
    ]
    if not raum_spalten or df.empty:
        return KomfortErgebnis({}, None, None, Bewertung.OK)

    daten = df[raum_spalten].sort_index(kind="stable").apply(pd.to_numeric, errors="coerce")
    delta_s = daten.index.to_series().shift(-1).sub(daten.index.to_series()).dt.total_seconds()
    # Große Lücken werden nicht als durchgehende Zeit unter bzw. über Soll gewertet.
    intervalle_gueltig = delta_s.gt(0) & delta_s.le(cfg.max_datenluecke_min * 60)
    anteile: dict[str, float] = {}
    mitteltemperaturen: dict[str, float] = {}
    soll_abweichungen: dict[str, float] = {}
    befunde: list[Befund] = []

    for spalte in raum_spalten:
        raum = spalte[5:-2]
        temperatur = daten[spalte]
        gueltige_werte = temperatur.notna()
        if raum in cfg.raum_soll_c:
            soll_c = cfg.raum_soll_c[raum]
            unter_soll = temperatur < soll_c - cfg.raum_anteil_toleranz_k
            intervalle = intervalle_gueltig & gueltige_werte & gueltige_werte.shift(-1, fill_value=False)
            dauer_s = delta_s.where(intervalle, 0.0)
            gesamte_dauer_s = float(dauer_s.sum())
            if gesamte_dauer_s > 0:
                zeit_unter_soll = float(dauer_s.where(unter_soll, 0.0).sum())
                anteile[raum] = round(zeit_unter_soll / gesamte_dauer_s, 3)

            unter_warnschwelle = temperatur < soll_c - cfg.raum_toleranz_k
            laufzeit_s = 0.0
            maximale_laufzeit_s = 0.0
            for zeit_s, ist_gueltig, ist_unter in zip(
                delta_s, intervalle, unter_warnschwelle & unter_warnschwelle.shift(-1, fill_value=False)
            ):
                if ist_gueltig and ist_unter:
                    laufzeit_s += zeit_s
                    maximale_laufzeit_s = max(maximale_laufzeit_s, laufzeit_s)
                else:
                    laufzeit_s = 0.0

            if maximale_laufzeit_s > cfg.raum_unter_soll_max_stunden * 3600:
                befunde.append(Befund(
                    "A5",
                    Bewertung.WARNUNG,
                    f"Der Raum {raum} liegt länger als {cfg.raum_unter_soll_max_stunden:g} h "
                    f"unter {soll_c - cfg.raum_toleranz_k:.1f} °C "
                    f"(Soll {soll_c:.1f} °C).",
                ))
        if gueltige_werte.any():
            if intervalle_gueltig.any():
                gewichtete_dauer = delta_s.where(intervalle_gueltig & gueltige_werte, 0.0)
                gewichtete_dauer = gewichtete_dauer.where(gueltige_werte.shift(-1, fill_value=False), 0.0)
                dauer_summe = float(gewichtete_dauer.sum())
                if dauer_summe > 0:
                    mitteltemperaturen[raum] = float(
                        (temperatur.fillna(0.0) * gewichtete_dauer).sum() / dauer_summe
                    )
                else:
                    mitteltemperaturen[raum] = float(temperatur.mean())
            else:
                mitteltemperaturen[raum] = float(temperatur.mean())
            if raum in cfg.raum_soll_c:
                soll_abweichungen[raum] = mitteltemperaturen[raum] - cfg.raum_soll_c[raum]

            if (temperatur < cfg.raum_kritisch_c).any():
                niedrigste_temperatur = float(temperatur.min())
                befunde.append(Befund(
                    "A6",
                    Bewertung.KRITISCH,
                    f"Der Raum {raum} ist mit {niedrigste_temperatur:.1f} °C kälter als "
                    f"{cfg.raum_kritisch_c:.1f} °C.",
                ))

    kaeltester_raum = min(mitteltemperaturen, key=mitteltemperaturen.get, default=None)
    kaelteste_mitteltemperatur = (
        round(mitteltemperaturen[kaeltester_raum], 1) if kaeltester_raum is not None else None
    )
    sortierte_abweichungen = sorted(soll_abweichungen.items(), key=lambda eintrag: eintrag[1])
    if (
        len(sortierte_abweichungen) > 1
        and sortierte_abweichungen[1][1] - sortierte_abweichungen[0][1]
        > cfg.raum_abgleich_differenz_k
    ):
        raum = sortierte_abweichungen[0][0]
        befunde.append(Befund(
            "KOMFORT",
            Bewertung.HINWEIS,
            f"Der Raum {raum} bleibt im Vergleich zu den anderen Räumen deutlich hinter seinem "
            "Sollwert zurück. Prüfe den hydraulischen Abgleich.",
        ))

    bewertung = max(
        (befund.bewertung for befund in befunde),
        key=lambda wert: list(Bewertung).index(wert),
        default=Bewertung.OK,
    )
    return KomfortErgebnis(
        anteile,
        kaeltester_raum,
        kaelteste_mitteltemperatur,
        bewertung,
        befunde,
    )
