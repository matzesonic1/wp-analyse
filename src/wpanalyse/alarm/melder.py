"""Schnittstelle und Implementierung für Alarm-Benachrichtigungen."""

import os
from typing import Protocol
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class Melder(Protocol):
    """Struktureller Vertrag für austauschbare Benachrichtigungskanäle."""

    def sende(self, nachricht: str) -> None:
        """Sendet eine formatierte Alarmnachricht."""


class NtfyMelder:
    """Sendet UTF-8-Textnachrichten an ein ntfy-Thema."""

    def __init__(
        self,
        thema: str | None = None,
        server_url: str | None = None,
        token: str | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        """Konfiguriert ntfy-Ziel, optionale Authentifizierung und Timeout.

        Fehlende Werte werden, sofern vorhanden, aus ``NTFY_TOPIC``,
        ``NTFY_URL`` und ``NTFY_TOKEN`` übernommen.
        """
        self.thema = thema or os.getenv("NTFY_TOPIC")
        self.server_url = (server_url or os.getenv("NTFY_URL") or "https://ntfy.sh").rstrip("/")
        self.token = token or os.getenv("NTFY_TOKEN")
        self.timeout_s = timeout_s

        if not self.thema:
            raise ValueError("Das ntfy-Thema muss über NTFY_TOPIC oder thema angegeben werden.")
        if urlsplit(self.server_url).scheme not in {"http", "https"}:
            raise ValueError("NTFY_URL muss eine HTTP- oder HTTPS-Adresse sein.")

    def sende(self, nachricht: str) -> None:
        """Sendet die Nachricht per HTTP-POST an das konfigurierte Thema."""
        url = f"{self.server_url}/{quote(self.thema, safe='')}"
        headers = {"Content-Type": "text/plain; charset=utf-8"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        anfrage = Request(url, data=nachricht.encode("utf-8"), headers=headers, method="POST")
        with urlopen(anfrage, timeout=self.timeout_s):
            pass
