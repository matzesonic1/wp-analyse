"""Erstellt einen laienverständlichen Markdown-Tagesbericht."""

from datetime import date

import pandas as pd

from ..analyse.effizienz import analysiere_effizienz
from ..analyse.spreizung import analysiere_spreizung
from ..config import Config
from ..models import Befund, Bewertung


def erstelle_tagesbericht(
    df: pd.DataFrame, cfg: Config, tag: date | str | None = None
) -> str:
    """Erstellt einen Bericht für den angegebenen oder letzten Messtag."""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Der DataFrame benötigt einen DatetimeIndex.")

    if tag is None:
        tag_datum = df.index[-1].date() if not df.empty else None
    else:
        tag_datum = pd.Timestamp(tag).date()
    tag_text = tag_datum.isoformat() if tag_datum else "unbekannt"

    if tag_datum is None:
        return f"# Tagesbericht – {tag_text}\n\nKeine Messwerte vorhanden."

    tagesdaten = df.loc[df.index.date == tag_datum].sort_index()
    if tagesdaten.empty:
        return f"# Tagesbericht – {tag_text}\n\nFür diesen Tag liegen keine Messwerte vor."

    befunde: list[Befund] = []
    zeilen = [f"# Tagesbericht – {tag_text}", "", "## Kennzahlen"]

    effizienz = analysiere_effizienz(tagesdaten, cfg)
    befunde.extend(effizienz.befunde)
    tages_az = effizienz.tages_az.get(tag_text)
    if tages_az is None:
        zeilen.append(f"- **Arbeitszahl (AZ):** nicht verfügbar ({_az_fehlgrund(tagesdaten)})")
    else:
        zeilen.append(f"- **Arbeitszahl (AZ):** {tages_az:.2f}")

    starts, laufzeit_std, abdeckung_std, zykluslaufzeit_min = _taktungswerte(tagesdaten, cfg)
    if starts is None:
        zeilen.append("- **Verdichterstarts:** nicht verfügbar (keine ausreichenden Messwerte)")
        zeilen.append("- **Verdichterlaufzeit:** nicht verfügbar (keine ausreichenden Messwerte)")
    else:
        zeilen.append(f"- **Verdichterstarts:** {starts} im erfassten Zeitraum")
        if laufzeit_std is None:
            zeilen.append("- **Verdichterlaufzeit:** nicht verfügbar (Zeitabstände fehlen)")
        else:
            zeilen.append(
                f"- **Verdichterlaufzeit:** etwa {laufzeit_std:.1f} h "
                "(aus den erfassten Messintervallen geschätzt)"
            )
        zeilen.append(f"- **Messabdeckung:** etwa {abdeckung_std:.1f} h")
        if zykluslaufzeit_min is not None:
            zeilen.append(f"- **Mittlere Laufzeit je Zyklus:** {zykluslaufzeit_min:.1f} min")

        warnung = (
            abdeckung_std >= 24
            and starts > cfg.max_starts_pro_tag
        ) or (
            zykluslaufzeit_min is not None
            and zykluslaufzeit_min < cfg.min_zykluslaufzeit_min
        )
        hinweis = (
            abdeckung_std >= 24
            and starts > cfg.hinweis_starts_pro_tag
        ) or (
            zykluslaufzeit_min is not None
            and zykluslaufzeit_min < cfg.ziel_zykluslaufzeit_min
        )
        if warnung or hinweis:
            grunde = []
            if abdeckung_std >= 24 and starts > min(
                cfg.max_starts_pro_tag, cfg.hinweis_starts_pro_tag
            ):
                grunde.append(f"{starts} Verdichterstarts")
            if zykluslaufzeit_min is not None and zykluslaufzeit_min < cfg.ziel_zykluslaufzeit_min:
                grunde.append(f"mittlere Zykluslaufzeit {zykluslaufzeit_min:.0f} min")
            befunde.append(
                Befund(
                    "A1",
                    Bewertung.WARNUNG if warnung else Bewertung.HINWEIS,
                    f"Die Taktung sollte beobachtet werden: {'; '.join(grunde)}. "
                    "Häufige Starts und kurze Zyklen können den Verdichter belasten.",
                )
            )

    if {"vorlauf_c", "ruecklauf_c", "verdichter_an"}.issubset(tagesdaten.columns):
        spreizung = analysiere_spreizung(tagesdaten, cfg)
        befunde.extend(spreizung.befunde)
        verdichter = tagesdaten["verdichter_an"].fillna(False).astype(bool)
        if verdichter.any() and spreizung.mittlere_spreizung_k > 0:
            zeilen.append(f"- **Mittlere Spreizung im Verdichterbetrieb:** {spreizung.mittlere_spreizung_k:.1f} K")
        else:
            zeilen.append("- **Spreizung:** nicht verfügbar (keine passenden Messwerte im Verdichterbetrieb)")
    else:
        zeilen.append("- **Spreizung:** nicht verfügbar (Vorlauf, Rücklauf oder Verdichterstatus fehlt)")

    raum_zeilen, raum_befunde = _raumkomfort(tagesdaten, cfg)
    zeilen.append("")
    zeilen.append("## Raumkomfort")
    zeilen.extend(raum_zeilen)
    befunde.extend(raum_befunde)

    zeilen.extend(["", "## Auffälligkeiten"])
    if befunde:
        zeilen.extend(f"- **{befund.regel_id} ({befund.bewertung.value}):** {befund.text}" for befund in befunde)
    else:
        zeilen.append("Keine Auffälligkeiten in den auswertbaren Messwerten erkannt.")

    return "\n".join(zeilen)


def _az_fehlgrund(df: pd.DataFrame) -> str:
    fehlende = {"waerme_kwh", "strom_kwh"} - set(df.columns)
    if fehlende:
        return f"{', '.join(sorted(fehlende))} fehlt"
    return "keine gültigen Wärme- und Stromenergiewerte"


def _taktungswerte(
    df: pd.DataFrame, cfg: Config
) -> tuple[int | None, float | None, float, float | None]:
    if "verdichter_an" not in df:
        return None, None, 0.0, None

    status = df["verdichter_an"].astype("boolean")
    if status.notna().sum() < 2:
        return None, None, 0.0, None

    zeitabstaende = df.index.to_series().diff().dt.total_seconds()
    gueltige_abstaende = zeitabstaende[zeitabstaende > 0]
    if gueltige_abstaende.empty:
        return None, None, 0.0, None
    max_luecke_s = cfg.max_datenluecke_min * 60
    gueltige_abstaende = gueltige_abstaende[gueltige_abstaende <= max_luecke_s]
    if gueltige_abstaende.empty:
        return None, None, 0.0, None
    abtast_s = float(gueltige_abstaende.median())
    abdeckung_std = min(
        24.0,
        (float(gueltige_abstaende.sum()) + abtast_s) / 3600,
    )

    vorher = status.shift(1)
    luecken_ok = zeitabstaende.le(max_luecke_s)
    starts = int(
        (status.eq(True) & vorher.eq(False) & luecken_ok).fillna(False).sum()
    )
    laufzeit_std = 0.0
    for position in range(len(status) - 1):
        if (
            pd.notna(status.iloc[position])
            and bool(status.iloc[position])
            and 0 < zeitabstaende.iloc[position + 1] <= max_luecke_s
        ):
            laufzeit_std += max(
                (df.index[position + 1] - df.index[position]).total_seconds(), 0
            ) / 3600

    zyklus_minuten: list[float] = []
    start_zeit = None
    for position, (zeit, zustand, vorheriger) in enumerate(zip(df.index, status, vorher, strict=False)):
        if (
            pd.isna(zustand)
            or pd.isna(vorheriger)
            or position == 0
            or not 0 < zeitabstaende.iloc[position] <= max_luecke_s
        ):
            start_zeit = None
            continue
        if bool(zustand) and not bool(vorheriger):
            start_zeit = zeit
        elif not bool(zustand) and bool(vorheriger) and start_zeit is not None:
            zyklus_minuten.append((zeit - start_zeit).total_seconds() / 60)
            start_zeit = None

    mittel_zyklus_min = sum(zyklus_minuten) / len(zyklus_minuten) if zyklus_minuten else None
    return starts, laufzeit_std, abdeckung_std, mittel_zyklus_min


def _raumkomfort(df: pd.DataFrame, cfg: Config) -> tuple[list[str], list[Befund]]:
    raum_spalten = sorted(
        spalte for spalte in df.columns
        if spalte.startswith("raum_") and spalte.endswith("_c")
    )
    if not raum_spalten:
        return ["Keine Raumtemperaturen vorhanden."], []

    zeitabstaende = df.index.to_series().diff().dt.total_seconds()
    max_luecke_s = cfg.max_datenluecke_min * 60
    zeilen: list[str] = []
    befunde: list[Befund] = []
    for spalte in raum_spalten:
        raum = spalte[5:-2]
        soll_c = cfg.raum_soll_c.get(raum)
        temperatur = df[spalte].dropna()
        if temperatur.empty:
            zeilen.append(f"- **{raum}:** nicht verfügbar (keine Temperaturmesswerte)")
            continue

        if (temperatur < cfg.raum_kritisch_c).any():
            tiefster_wert = float(temperatur.min())
            befunde.append(
                Befund(
                    "A6",
                    Bewertung.KRITISCH,
                    f"{raum} fiel auf {tiefster_wert:.1f} °C und damit unter "
                    f"die kritische Grenze von {cfg.raum_kritisch_c:.1f} °C.",
                )
            )

        if soll_c is None:
            zeilen.append(f"- **{raum}:** nicht bewertbar (Solltemperatur nicht konfiguriert)")
            continue

        unter_grenze_c = soll_c - cfg.raum_toleranz_k
        unter_soll = df[spalte] < unter_grenze_c
        anteil_unter = float(unter_soll.sum() / temperatur.size * 100)
        zeilen.append(
            f"- **{raum}:** {anteil_unter:.0f} % der Messwerte unter "
            f"{unter_grenze_c:.1f} °C (Soll {soll_c:.1f} °C)"
        )

        unter_stunden = sum(
            zeitabstaende.iloc[position + 1] / 3600
            for position in range(len(df) - 1)
            if (
                pd.notna(df[spalte].iloc[position])
                and df[spalte].iloc[position] < unter_grenze_c
                and 0 < zeitabstaende.iloc[position + 1] <= max_luecke_s
            )
        )
        if unter_stunden > cfg.raum_warnung_dauer_std:
            befunde.append(
                Befund(
                    "A5",
                    Bewertung.WARNUNG,
                    f"{raum} lag insgesamt etwa {unter_stunden:.1f} h unter "
                    f"{unter_grenze_c:.1f} °C (Soll minus {cfg.raum_toleranz_k:.1f} K).",
                )
            )
    return zeilen, befunde
