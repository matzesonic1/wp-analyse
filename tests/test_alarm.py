"""Tests für Alarmformatierung, Entprellung und den ntfy-Melder."""

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from wpanalyse.alarm import AlarmManager, NtfyMelder
from wpanalyse.models import Befund, Bewertung


class FakeMelder:
    """Sammelt versendete Nachrichten für Assertions ohne Netzwerkzugriff."""

    def __init__(self):
        """Initialisiert die Liste der aufgezeichneten Nachrichten."""
        self.nachrichten = []

    def sende(self, nachricht: str) -> None:
        """Speichert eine Nachricht, statt sie tatsächlich zu versenden."""
        self.nachrichten.append(nachricht)


def test_meldet_befunde_mit_passendem_schweregrad():
    """Jeder nicht-ok-Befund erhält die zugehörige Schweregradbezeichnung."""
    melder = FakeMelder()
    manager = AlarmManager(melder)

    manager.verarbeite(
        [
            Befund("A1", Bewertung.HINWEIS, "Info-Text"),
            Befund("A2", Bewertung.WARNUNG, "Warn-Text"),
            Befund("A3", Bewertung.KRITISCH, "Kritisch-Text"),
            Befund("A4", Bewertung.OK, "Kein Alarm"),
        ]
    )

    assert melder.nachrichten == [
        "Info: A1: Info-Text",
        "Warnung: A2: Warn-Text",
        "Kritisch: A3: Kritisch-Text",
    ]


def test_entprellt_wiederholungen_fuer_sechs_stunden():
    """Wiederholungen werden erst nach Ablauf der Entprellzeit gesendet."""
    melder = FakeMelder()
    manager = AlarmManager(melder)
    befund = Befund("A1", Bewertung.WARNUNG, "Warnung")
    start = datetime(2026, 1, 1, tzinfo=UTC)

    manager.verarbeite([befund], start)
    manager.verarbeite([befund], start + timedelta(hours=5, minutes=59))
    manager.verarbeite([befund], start + timedelta(hours=6))

    assert melder.nachrichten == ["Warnung: A1: Warnung", "Warnung: A1: Warnung"]


def test_sendet_einmalige_entwarnung_wenn_befund_verschwindet():
    """Ein nicht mehr aktiver Befund löst genau eine Entwarnung aus."""
    melder = FakeMelder()
    manager = AlarmManager(melder)
    befund = Befund("A1", Bewertung.WARNUNG, "Warnung")

    manager.verarbeite([befund])
    manager.verarbeite([])
    manager.verarbeite([])

    assert melder.nachrichten == ["Warnung: A1: Warnung", "Entwarnung: A1 ist behoben."]


def test_ntfy_melder_sendet_nachricht_mit_konfiguration():
    """Der ntfy-Melder baut POST-Anfrage, Ziel und Authentifizierung korrekt auf."""
    melder = NtfyMelder("waermepumpe", "https://ntfy.example", "test-token-not-real")

    with patch("wpanalyse.alarm.melder.urlopen", return_value=nullcontext()) as urlopen_mock:
        melder.sende("Warnung: A1")

    anfrage = urlopen_mock.call_args.args[0]
    assert anfrage.full_url == "https://ntfy.example/waermepumpe"
    assert anfrage.get_method() == "POST"
    assert anfrage.data == b"Warnung: A1"
    assert anfrage.get_header("Authorization").startswith("Bearer ")
    assert anfrage.get_header("Authorization").endswith("not-real")
