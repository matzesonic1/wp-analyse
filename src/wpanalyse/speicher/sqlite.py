"""Speichert Messwerte in einer SQLite-Datenbank."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Self

import pandas as pd


class SQLiteSpeicher:
    """Speichert DataFrames mit Zeitindex und lädt sie für einen Zeitraum."""

    def __init__(self, pfad: str | Path):
        if str(pfad) != ":memory:":
            Path(pfad).parent.mkdir(parents=True, exist_ok=True)
        self._verbindung = sqlite3.connect(pfad)
        with self._verbindung:
            self._verbindung.execute(
                "CREATE TABLE IF NOT EXISTS messwerte "
                "(zeit_ns INTEGER PRIMARY KEY, daten TEXT NOT NULL)"
            )
            self._verbindung.execute(
                "CREATE TABLE IF NOT EXISTS metadaten "
                "(schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL)"
            )

    def speichern(self, df: pd.DataFrame) -> None:
        """Speichert Messwerte anhand ihres DatetimeIndex."""
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("Der DataFrame benötigt einen DatetimeIndex.")
        if df.index.hasnans:
            raise ValueError("Der Zeitindex darf keine fehlenden Werte enthalten.")
        if not all(isinstance(spalte, str) for spalte in df.columns):
            raise TypeError("Die Spaltennamen müssen Zeichenketten sein.")

        zeitindex = df.index
        if zeitindex.tz is None:
            zeitindex = zeitindex.tz_localize("UTC")
        else:
            zeitindex = zeitindex.tz_convert("UTC")
        zeiten_ns = zeitindex.as_unit("ns").asi8
        datensaetze = json.loads(df.to_json(orient="records", date_format="iso"))
        with self._verbindung:
            self._verbindung.executemany(
                "INSERT INTO messwerte (zeit_ns, daten) VALUES (?, ?) "
                "ON CONFLICT(zeit_ns) DO UPDATE SET daten = excluded.daten",
                [
                    (int(zeit_ns), json.dumps(datensatz, ensure_ascii=False))
                    for zeit_ns, datensatz in zip(zeiten_ns, datensaetze, strict=True)
                ],
            )
            vorhandene_spalten = self._verbindung.execute(
                "SELECT wert FROM metadaten WHERE schluessel = 'spalten'"
            ).fetchone()
            spalten = json.loads(vorhandene_spalten[0]) if vorhandene_spalten else []
            spalten.extend(spalte for spalte in df.columns if spalte not in spalten)
            self._verbindung.execute(
                "INSERT INTO metadaten (schluessel, wert) VALUES ('spalten', ?) "
                "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert",
                (json.dumps(spalten, ensure_ascii=False),),
            )

    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        """Lädt Messwerte im Zeitraum [von, bis) mit UTC-DatetimeIndex."""
        von_ns = self._zeit_ns(von)
        bis_ns = self._zeit_ns(bis)
        zeilen = self._verbindung.execute(
            "SELECT zeit_ns, daten FROM messwerte "
            "WHERE zeit_ns >= ? AND zeit_ns < ? ORDER BY zeit_ns",
            (von_ns, bis_ns),
        ).fetchall()
        metadaten = self._verbindung.execute(
            "SELECT wert FROM metadaten WHERE schluessel = 'spalten'"
        ).fetchone()
        spalten = json.loads(metadaten[0]) if metadaten else []
        df = pd.DataFrame.from_records(
            [json.loads(daten) for _, daten in zeilen],
            columns=spalten,
        )
        df.index = pd.to_datetime([zeit_ns for zeit_ns, _ in zeilen], unit="ns", utc=True)
        return df

    @staticmethod
    def _zeit_ns(zeit: datetime) -> int:
        zeitstempel = pd.Timestamp(zeit)
        if zeitstempel.tz is None:
            zeitstempel = zeitstempel.tz_localize("UTC")
        else:
            zeitstempel = zeitstempel.tz_convert("UTC")
        return zeitstempel.value

    def close(self) -> None:
        """Schließt die Datenbankverbindung."""
        self._verbindung.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
