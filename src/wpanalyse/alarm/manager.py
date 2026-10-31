"""Entprellung und Entwarnung für Analysebefunde."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from ..models import Befund, Bewertung
from .melder import Melder


class AlarmManager:
    """Versendet neue Befunde, begrenzt Wiederholungen und meldet Entwarnungen."""

    def __init__(self, melder: Melder, entprellzeit: timedelta = timedelta(hours=6)) -> None:
        if entprellzeit < timedelta(0):
            raise ValueError("Die Entprellzeit darf nicht negativ sein.")
        self.melder = melder
        self.entprellzeit = entprellzeit
        self._letzte_meldung: dict[str, datetime] = {}
        self._aktive_befunde: dict[str, Befund] = {}

    def verarbeite(self, befunde: Iterable[Befund], jetzt: datetime | None = None) -> None:
        """Verarbeitet den vollständigen aktuellen Befundstand."""
        zeitpunkt = jetzt or datetime.now(UTC)
        if zeitpunkt.tzinfo is None or zeitpunkt.utcoffset() is None:
            raise ValueError("Der Zeitpunkt muss eine Zeitzone enthalten.")

        aktuelle_befunde = {
            befund.regel_id: befund
            for befund in befunde
            if befund.bewertung != Bewertung.OK
        }

        for regel_id in self._aktive_befunde.keys() - aktuelle_befunde.keys():
            self.melder.sende(f"Entwarnung: {regel_id} ist behoben.")
            del self._aktive_befunde[regel_id]

        for regel_id, befund in aktuelle_befunde.items():
            letzte_meldung = self._letzte_meldung.get(regel_id)
            if letzte_meldung is None or zeitpunkt - letzte_meldung >= self.entprellzeit:
                bezeichnung = {
                    Bewertung.HINWEIS: "Info",
                    Bewertung.WARNUNG: "Warnung",
                    Bewertung.KRITISCH: "Kritisch",
                }[befund.bewertung]
                self.melder.sende(f"{bezeichnung}: {regel_id}: {befund.text}")
                self._letzte_meldung[regel_id] = zeitpunkt
            self._aktive_befunde[regel_id] = befund
