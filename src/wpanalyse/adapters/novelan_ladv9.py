"""Liest und konvertiert Novelan-Messwerte über die Home-Assistant-REST-API."""

import json
import os
from collections.abc import Mapping
from datetime import datetime
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .base import DatenAdapter

_UMGEBUNGSMAPPING = {
    "aussen_c": "NOVELAN_ENTITY_AUSSEN_C",
    "vorlauf_c": "NOVELAN_ENTITY_VORLAUF_C",
    "ruecklauf_c": "NOVELAN_ENTITY_RUECKLAUF_C",
    "verdichter_an": "NOVELAN_ENTITY_VERDICHTER_AN",
    "verdichter_hz": "NOVELAN_ENTITY_VERDICHTER_HZ",
    "leistung_w": "NOVELAN_ENTITY_LEISTUNG_W",
    "strom_kwh": "NOVELAN_ENTITY_STROM_KWH",
    "waerme_kwh": "NOVELAN_ENTITY_WAERME_KWH",
    "heizstab_an": "NOVELAN_ENTITY_HEIZSTAB_AN",
    "betriebsart": "NOVELAN_ENTITY_BETRIEBSART",
    "warmwasser_c": "NOVELAN_ENTITY_WARMWASSER_C",
    "stoerung": "NOVELAN_ENTITY_STOERUNG",
}

_BOOL_FELDER = {"verdichter_an", "heizstab_an"}
_ZAHL_FELDER = {
    "aussen_c",
    "vorlauf_c",
    "ruecklauf_c",
    "verdichter_hz",
    "leistung_w",
    "strom_kwh",
    "waerme_kwh",
    "warmwasser_c",
}


class NovelanLadv9Adapter(DatenAdapter):
    """Liest konfigurierte Home-Assistant-Entitäten als Novelan-Messwerte.

    URL, Token und Entitäts-IDs können direkt übergeben oder aus
    Umgebungsvariablen gelesen werden.
    """

    def __init__(
        self,
        ha_url: str | None = None,
        token: str | None = None,
        sensoren: Mapping[str, str] | None = None,
        timeout: float = 30,
    ):
        """Legt API-Zugang, Feldzuordnungen und Anfrage-Timeout fest.

        ``sensoren`` ordnet Projektfeldnamen den Home-Assistant-Entity-IDs zu.
        Ohne explizite Zuordnung werden konfigurierte Entity-IDs aus der
        jeweiligen ``NOVELAN_ENTITY_*``-Umgebungsvariable gelesen.
        """
        self.ha_url = (ha_url or os.getenv("HA_URL", "")).rstrip("/")
        self.token = token or os.getenv("HA_TOKEN", "")
        self.sensoren = (
            dict(sensoren)
            if sensoren is not None
            else {
                feld: os.getenv(umgebungsvariable, "")
                for feld, umgebungsvariable in _UMGEBUNGSMAPPING.items()
                if os.getenv(umgebungsvariable)
            }
        )
        self.timeout = timeout
        if not self.ha_url or not self.token:
            raise ValueError("HA_URL und HA_TOKEN müssen gesetzt sein.")
        if not self.sensoren or any(not entity_id for entity_id in self.sensoren.values()):
            raise ValueError("Mindestens eine Novelan-Home-Assistant-Entität muss konfiguriert sein.")

    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        """Lädt den Entity-Verlauf im halboffenen Zeitraum ``[von, bis)``."""
        von_utc = _utc_zeit(von)
        bis_utc = _utc_zeit(bis)
        parameter = urlencode(
            {
                "end_time": bis_utc.isoformat().replace("+00:00", "Z"),
                "filter_entity_id": ",".join(self.sensoren.values()),
            }
        )
        url = (
            f"{self.ha_url}/api/history/period/"
            f"{quote(von_utc.isoformat().replace('+00:00', 'Z'), safe='')}?{parameter}"
        )
        verlauf = self._anfrage(url)
        zustaende = [zustand for entitaetsverlauf in verlauf for zustand in entitaetsverlauf]
        df = self._als_dataframe(zustaende)
        return df[(df.index >= von_utc) & (df.index < bis_utc)]

    def aktuell(self) -> pd.DataFrame:
        """Lädt die derzeitigen Zustände aller konfigurierten Entitäten."""
        zustaende = self._anfrage(f"{self.ha_url}/api/states")
        return self._als_dataframe(
            zustand for zustand in zustaende if zustand.get("entity_id") in self.sensoren.values()
        )

    def _anfrage(self, url: str) -> list:
        """Sendet eine authentifizierte GET-Anfrage und dekodiert die JSON-Antwort."""
        anfrage = Request(url, headers={"Authorization": "Bearer " + self.token})
        with urlopen(anfrage, timeout=self.timeout) as antwort:
            return json.load(antwort)

    def _als_dataframe(self, zustaende) -> pd.DataFrame:
        """Ordnet API-Zustände nach Zeit und Projektfeld zu einem DataFrame.

        Zustände mit identischem Zeitstempel werden in derselben Zeile gesammelt;
        nicht konfigurierte Entitäten und Zustände ohne Zeitangabe werden ignoriert.
        """
        entity_felder: dict[str, list[str]] = {}
        for feld, entity_id in self.sensoren.items():
            entity_felder.setdefault(entity_id, []).append(feld)

        zeilen = {}
        for zustand in zustaende:
            entity_id = zustand.get("entity_id")
            if entity_id not in entity_felder:
                continue
            zeitwert = zustand.get("last_changed") or zustand.get("last_updated")
            if not zeitwert:
                continue
            zeit = _utc_zeit(pd.Timestamp(zeitwert).to_pydatetime())
            zeile = zeilen.setdefault(zeit, {})
            for feld in entity_felder[entity_id]:
                zeile[feld] = _messwert(feld, zustand.get("state"))

        if not zeilen:
            index = pd.DatetimeIndex([], tz="UTC")
            return pd.DataFrame(columns=self.sensoren, index=index)
        df = pd.DataFrame.from_dict(zeilen, orient="index").sort_index()
        df.index = pd.DatetimeIndex(df.index)
        return df.reindex(columns=self.sensoren)


def _utc_zeit(zeit: datetime) -> pd.Timestamp:
    """Interpretiert naive Zeiten als UTC und konvertiert zonierte Zeiten nach UTC."""
    zeitstempel = pd.Timestamp(zeit)
    if zeitstempel.tzinfo is None:
        return zeitstempel.tz_localize("UTC")
    return zeitstempel.tz_convert("UTC")


def _messwert(feld: str, zustand: str | None):
    """Konvertiert einen Home-Assistant-Zustand entsprechend dem Projektfeld.

    Nicht verfügbare, unbekannte oder nicht parsebare Werte werden als
    ``pd.NA`` zurückgegeben.
    """
    if zustand is None or str(zustand).lower() in {"", "unknown", "unavailable", "none"}:
        return pd.NA
    if feld in _BOOL_FELDER:
        wert = str(zustand).lower()
        if wert in {"on", "true", "1"}:
            return True
        if wert in {"off", "false", "0"}:
            return False
        return pd.NA
    if feld in _ZAHL_FELDER or feld.startswith("raum_") and feld.endswith("_c"):
        try:
            return float(zustand)
        except (TypeError, ValueError):
            return pd.NA
    return str(zustand)
