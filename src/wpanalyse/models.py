"""Gemeinsames Datenmodell. Alle Adapter liefern Messwerte in diesem Format."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Bewertung(str, Enum):
    """Schweregrad eines Analysebefunds in aufsteigender Reihenfolge."""

    OK = "ok"
    HINWEIS = "hinweis"
    WARNUNG = "warnung"
    KRITISCH = "kritisch"


@dataclass
class Messwert:
    """Messwerte zu einem Zeitpunkt; nicht erfasste Einzelwerte sind ``None``.

    Temperaturen werden in Grad Celsius, Leistung in Watt und Wärmeleistung in
    Watt angegeben. Der Zeitstempel sollte eine Zeitzone enthalten.
    """

    zeit: datetime
    aussen_c: float | None = None
    vorlauf_c: float | None = None
    ruecklauf_c: float | None = None
    verdichter_an: bool | None = None
    leistung_w: float | None = None
    waerme_w: float | None = None
    heizstab_an: bool | None = None
    betriebsart: str | None = None  # heizen | warmwasser | abtauen | aus
    warmwasser_c: float | None = None
    stoerung: str | None = None
    raeume_c: dict[str, float] = field(default_factory=dict)  # z. B. {"wohnzimmer": 20.8}


@dataclass(frozen=True)
class Stoerung:
    """Unverändert übernommener Störungseintrag einer Anlage."""

    ereignis_id: str
    beginn: datetime
    ende: datetime | None = None
    fehlercode: str | None = None
    beschreibung_roh: str | None = None
    quelle: str | None = None


@dataclass(frozen=True)
class WartungReparatur:
    """Dokumentierter Wartungs- oder Reparatureintrag."""

    ereignis_id: str
    zeit: datetime
    massnahme: str
    komponente: str | None = None
    bestaetigter_fehler: str | None = None
    quelle: str | None = None


@dataclass
class Befund:
    """Verständlich formulierter Befund aus einer Regel oder Analyse.

    ``regel_id`` ordnet den Befund einer Regel zu, ``bewertung`` gibt seine
    Schwere an und ``text`` beschreibt die Beobachtung für den Anwender.
    """

    regel_id: str
    bewertung: Bewertung
    text: str
