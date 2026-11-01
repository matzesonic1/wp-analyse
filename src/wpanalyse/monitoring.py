"""Orchestriert Analysen gespeicherter Messwerte und übergibt den Befundstand."""

from datetime import datetime

import pandas as pd

from .alarm import AlarmManager
from .analyse.effizienz import analysiere_effizienz
from .analyse.komfort import analysiere_komfort
from .analyse.spreizung import analysiere_spreizung
from .analyse.taktung import analysiere_taktung
from .config import Config
from .models import Befund, Bewertung
from .speicher import SQLiteSpeicher


def _nicht_auswertbar(regel_id: str, grund: str) -> Befund:
    """Erstellt einen Befund, der eine nicht prüfbare Regel kenntlich macht."""
    return Befund(regel_id, Bewertung.HINWEIS, f"{regel_id} nicht auswertbar: {grund}")


def pruefe_und_melde(
    speicher: SQLiteSpeicher,
    alarm_manager: AlarmManager,
    cfg: Config,
    von: datetime,
    bis: datetime,
) -> list[Befund]:
    """Analysiert den angefragten Zeitraum und übergibt alle aktuellen Befunde."""
    df = speicher.lese(von, bis).sort_index(kind="stable")
    befunde: list[Befund] = []
    nicht_auswertbar: list[Befund] = []

    if (
        df.empty
        or "verdichter_an" not in df
        or df["verdichter_an"].notna().sum() < 2
    ):
        nicht_auswertbar.append(_nicht_auswertbar("A1", "mindestens zwei Verdichtermesswerte werden benötigt"))
    else:
        befunde.extend(analysiere_taktung(df, cfg).befunde)

    effizienz = analysiere_effizienz(df, cfg)
    if not df.empty and {"waerme_kwh", "strom_kwh", "aussen_c"}.issubset(df.columns):
        waerme = pd.to_numeric(df["waerme_kwh"], errors="coerce")
        strom = pd.to_numeric(df["strom_kwh"], errors="coerce")
        aussen = pd.to_numeric(df["aussen_c"], errors="coerce")
        az_auswertbar = (waerme.notna() & strom.gt(0) & aussen.notna()).any()
    else:
        az_auswertbar = False
    befunde.extend(befund for befund in effizienz.befunde if befund.regel_id == "A2")
    if not az_auswertbar:
        nicht_auswertbar.append(
            _nicht_auswertbar("A2", "waerme_kwh, strom_kwh und aussen_c mit gültigen Werten werden benötigt")
        )

    heizstab_verfuegbar = (
        not df.empty
        and {"heizstab_an", "aussen_c"}.issubset(df.columns)
        and df["heizstab_an"].notna().any()
    )
    if heizstab_verfuegbar:
        heizstab_an = df["heizstab_an"].fillna(False).astype(bool)
        aussen = pd.to_numeric(df["aussen_c"], errors="coerce")
        heizstab_verfuegbar = not (heizstab_an & aussen.isna()).any()
    befunde.extend(befund for befund in effizienz.befunde if befund.regel_id == "A4")
    if not heizstab_verfuegbar:
        nicht_auswertbar.append(
            _nicht_auswertbar("A4", "heizstab_an und aussen_c mit gültigen Werten werden benötigt")
        )

    erforderliche_spalten = {"vorlauf_c", "ruecklauf_c", "verdichter_an"}
    if not df.empty and erforderliche_spalten.issubset(df.columns):
        verdichter_an = df["verdichter_an"].fillna(False).astype(bool)
        vorlauf = pd.to_numeric(df["vorlauf_c"], errors="coerce")
        ruecklauf = pd.to_numeric(df["ruecklauf_c"], errors="coerce")
        gueltige_spreizung = verdichter_an & vorlauf.notna() & ruecklauf.notna()
        if gueltige_spreizung.any():
            index = df.index[gueltige_spreizung]
            if index.max() - index.min() >= pd.Timedelta(days=30):
                befunde.extend(analysiere_spreizung(df, cfg).befunde)
            else:
                nicht_auswertbar.append(_nicht_auswertbar("A3", "mindestens 30 Tage Spreizungsdaten werden benötigt"))
        else:
            nicht_auswertbar.append(_nicht_auswertbar("A3", "keine gültigen Spreizungsdaten vorhanden"))
    else:
        nicht_auswertbar.append(
            _nicht_auswertbar("A3", "vorlauf_c, ruecklauf_c und verdichter_an werden benötigt")
        )

    komfort = analysiere_komfort(df, cfg)
    raum_spalten = {
        spalte[5:-2]: spalte
        for spalte in df.columns
        if spalte.startswith("raum_") and spalte.endswith("_c") and spalte[5:-2]
    }
    gueltige_raeume = {
        raum for raum, spalte in raum_spalten.items() if df[spalte].notna().any()
    }
    if len(df) > 1:
        zeitabstand = df.index.to_series().shift(-1).sub(df.index.to_series()).dt.total_seconds()
        intervalle_gueltig = zeitabstand.gt(0) & zeitabstand.le(cfg.max_datenluecke_min * 60)
        raeume_mit_intervall = {
            raum
            for raum, spalte in raum_spalten.items()
            if (
                intervalle_gueltig
                & df[spalte].notna()
                & df[spalte].notna().shift(-1, fill_value=False)
            ).any()
        }
    else:
        raeume_mit_intervall = set()
    sollraeume = set(cfg.raum_soll_c)
    fehlende_sollraeume = sollraeume - gueltige_raeume
    befunde.extend(befund for befund in komfort.befunde if befund.regel_id == "A5")
    if not sollraeume or not sollraeume.issubset(raeume_mit_intervall):
        nicht_auswertbar.append(
            _nicht_auswertbar("A5", "gültige Intervalle für konfigurierte Raumtemperaturen fehlen")
        )

    befunde.extend(befund for befund in komfort.befunde if befund.regel_id == "A6")
    if not gueltige_raeume or fehlende_sollraeume:
        nicht_auswertbar.append(_nicht_auswertbar("A6", "keine vollständigen Raumtemperaturen vorhanden"))

    befunde.extend(befund for befund in komfort.befunde if befund.regel_id == "KOMFORT")
    if len(sollraeume) < 2 or fehlende_sollraeume:
        nicht_auswertbar.append(_nicht_auswertbar("KOMFORT", "mindestens zwei Sollräume werden benötigt"))

    aktive_regeln = {befund.regel_id for befund in befunde}
    befunde.extend(
        befund for befund in nicht_auswertbar if befund.regel_id not in aktive_regeln
    )
    alarm_manager.verarbeite(befunde)
    return befunde
