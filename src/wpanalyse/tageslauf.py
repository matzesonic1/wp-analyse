"""Erzeugt Tagesberichte aus dem persistenten Messwertspeicher."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .bericht.tagesbericht import erstelle_tagesbericht
from .config import Config
from .speicher import SQLiteSpeicher


def erzeuge_tagesbericht(
    speicher: SQLiteSpeicher, cfg: Config, tag: date, ziel: Path
) -> Path:
    """Lädt die Messwerte eines UTC-Kalendertags und speichert den Markdown-Bericht."""
    von = datetime(tag.year, tag.month, tag.day, tzinfo=UTC)
    bis = von + timedelta(days=1)
    df = speicher.lese(von, bis)
    bericht = erstelle_tagesbericht(df, cfg, tag)
    ziel.write_text(bericht, encoding="utf-8")
    return ziel
