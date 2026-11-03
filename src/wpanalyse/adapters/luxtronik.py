"""Adapter für Luxtronik-2.x-Regler (Novelan/Alpha Innotec) über das LAN-Protokoll.

Es wird ausschließlich gelesen (Port 8889). Es werden niemals Parameter
geschrieben. Der Regler liefert keine Historie, daher gibt es nur ``aktuell()``.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from wpanalyse.adapters.base import DatenAdapter
from wpanalyse.config import LUXTRONIK_FELDER, LuxtronikConfig


def _standard_client(host: str, port: int) -> Any:
    """Öffnet eine lesende Verbindung über das Paket ``luxtronik``."""
    from luxtronik import Luxtronik

    return Luxtronik(host, port, safe=True)


class LuxtronikAdapter(DatenAdapter):
    """Liest Live-Messwerte vom Luxtronik-Regler und liefert sie im Projektformat."""

    def __init__(
        self,
        config: LuxtronikConfig | None = None,
        client_fabrik: Callable[[str, int], Any] = _standard_client,
        felder: dict[str, str] | None = None,
    ):
        """Speichert Konfiguration, Client-Fabrik (für Tests ersetzbar) und Feldzuordnung."""
        self._config = config or LuxtronikConfig.aus_umgebung()
        if not self._config.host:
            raise ValueError("Kein Host gesetzt: Umgebungsvariable LUXTRONIK_HOST angeben.")
        self._client_fabrik = client_fabrik
        self._felder = felder or LUXTRONIK_FELDER

    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        """Nicht unterstützt: Der Regler hält keine Historie vor."""
        raise NotImplementedError("Der Luxtronik-Regler liefert keine Historie; Monitor nutzen.")

    def aktuell(self) -> pd.DataFrame:
        """Fragt den Regler einmal ab und liefert eine Zeile mit UTC-Zeitstempel."""
        client = self._client_fabrik(self._config.host, self._config.port)
        zeile: dict[str, Any] = {}
        for feld, luxtronik_name in self._felder.items():
            eintrag = client.calculations.get(luxtronik_name)
            zeile[feld] = None if eintrag is None else eintrag.value
        if self._config.alle_calculations_speichern:
            zeile.update(self._weitere_werte(client, set(self._felder.values())))
        return self._in_projektformat(zeile)

    @staticmethod
    def _weitere_werte(client: Any, bereits: set[str]) -> dict[str, Any]:
        """Liefert alle übrigen benannten Calculations als Spalten ``lux_<name>``.

        Unbenannte Felder (``Unknown_*``) und Texte werden übersprungen.
        """
        alle = getattr(getattr(client, "calculations", None), "calculations", None) or {}
        werte: dict[str, Any] = {}
        for eintrag in alle.values():
            name = str(eintrag.name)
            if name in bereits or name.startswith("Unknown_"):
                continue
            if isinstance(eintrag.value, bool | int | float):
                werte[f"lux_{name}"] = eintrag.value
        return werte

    def _in_projektformat(self, roh: dict[str, Any]) -> pd.DataFrame:
        """Leitet abgeleitete Felder ab und baut den DataFrame mit UTC-Index."""
        zeile = dict(roh)
        betriebsart_roh = str(zeile.pop("betriebsart_roh", "") or "").strip().lower()
        zeile["betriebsart"] = self._config.betriebsart_zuordnung.get(betriebsart_roh, betriebsart_roh)
        zeile["verdichter_an"] = bool((zeile.get("verdichter_laufzeit_s") or 0) > 0)
        zeile["heizstab_an"] = bool(
            (zeile.get("heizstab1_laufzeit_s") or 0) > 0 or (zeile.get("heizstab2_laufzeit_s") or 0) > 0
        )
        index = pd.DatetimeIndex([datetime.now(UTC)])
        return pd.DataFrame([zeile], index=index)
