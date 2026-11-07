"""Startet den HA-Monitor mit der Konfiguration des Supervisor."""

import json
import os
from pathlib import Path

from wpanalyse.ha_monitor import main

_ENTITY_UMGEBUNGSMAPPING = {
    "entity_aussen_c": "NOVELAN_ENTITY_AUSSEN_C",
    "entity_vorlauf_c": "NOVELAN_ENTITY_VORLAUF_C",
    "entity_ruecklauf_c": "NOVELAN_ENTITY_RUECKLAUF_C",
    "entity_verdichter_an": "NOVELAN_ENTITY_VERDICHTER_AN",
    "entity_verdichter_hz": "NOVELAN_ENTITY_VERDICHTER_HZ",
    "entity_leistung_w": "NOVELAN_ENTITY_LEISTUNG_W",
    "entity_strom_kwh": "NOVELAN_ENTITY_STROM_KWH",
    "entity_waerme_kwh": "NOVELAN_ENTITY_WAERME_KWH",
    "entity_heizstab_an": "NOVELAN_ENTITY_HEIZSTAB_AN",
    "entity_betriebsart": "NOVELAN_ENTITY_BETRIEBSART",
    "entity_warmwasser_c": "NOVELAN_ENTITY_WARMWASSER_C",
    "entity_stoerung": "NOVELAN_ENTITY_STOERUNG",
}


def _optionen_laden() -> dict:
    """Liest Supervisor-Optionen, ohne Konfigurationswerte zu protokollieren."""
    try:
        with Path("/data/options.json").open(encoding="utf-8") as datei:
            optionen = json.load(datei)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Supervisor-Konfiguration kann nicht gelesen werden.") from exc
    if not isinstance(optionen, dict):
        raise TypeError("Supervisor-Konfiguration hat ein ungueltiges Format.")
    return optionen


def main_app() -> int:
    """Überträgt Konfigurationswerte in die Adapter-Umgebung und startet den Monitor."""
    optionen = _optionen_laden()
    os.environ["HA_URL"] = str(optionen.get("ha_url", ""))
    os.environ["HA_TOKEN"] = str(optionen.get("ha_token", ""))
    for option, variable in _ENTITY_UMGEBUNGSMAPPING.items():
        wert = str(optionen.get(option, "") or "")
        if wert:
            os.environ[variable] = wert
        else:
            os.environ.pop(variable, None)

    return main(
        [
            "--db",
            "/data/wp.sqlite",
            "--intervall",
            str(optionen.get("intervall_s", 60)),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main_app())
