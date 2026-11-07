"""Persistiert Messreihen und bestätigte Ereignisse in SQLite."""

import json
import math
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Self

import pandas as pd

from wpanalyse.models import Stoerung, WartungReparatur

_FELD_TYPEN = {
    "aussen_c": "REAL",
    "vorlauf_c": "REAL",
    "ruecklauf_c": "REAL",
    "verdichter_an": "INTEGER",
    "verdichter_hz": "REAL",
    "betriebsart": "TEXT",
    "heizstab_an": "INTEGER",
    "leistung_w": "REAL",
    "strom_kwh": "REAL",
    "strom_zaehler_kwh": "REAL",
    "waerme_w": "REAL",
    "waerme_kwh": "REAL",
    "waerme_zaehler_kwh": "REAL",
    "verdichter_starts_zaehler": "INTEGER",
    "verdichter_betriebszeit_zaehler_s": "REAL",
    "verdichter_laufzeit_intervall_s": "REAL",
    "warmwasser_c": "REAL",
    "ruecklauf_soll_c": "REAL",
    "quelle": "TEXT",
}
_BOOLEAN_FELDER = {"verdichter_an", "heizstab_an"}
_INTEGER_FELDER = {"verdichter_starts_zaehler"}
_RAUM_SPALTE = re.compile(r"^raum_(.+)_c$")


class SQLiteSpeicher:
    """Speichert Messreihen je Anlage mit UTC-Normalisierung und Zeitraumabfragen.

    Zeitstempel sind je Anlage eindeutig: Ein erneut gespeicherter Datensatz
    ersetzt den zuvor gespeicherten Wert desselben Zeitpunkts.
    """

    def __init__(self, pfad: str | Path, anlage_id: str = "standard"):
        """Öffnet oder erstellt die Datenbank für die angegebene Anlage."""
        if not anlage_id:
            raise ValueError("Die Anlagen-ID darf nicht leer sein.")
        if str(pfad) != ":memory:":
            Path(pfad).parent.mkdir(parents=True, exist_ok=True)
        self.anlage_id = anlage_id
        self._verbindung = sqlite3.connect(pfad)
        self._verbindung.execute("PRAGMA foreign_keys = ON")
        try:
            self._verbindung.execute("BEGIN")
            self._initialisiere_schema()
            self._migriere_altes_schema()
            self._verbindung.execute(
                "INSERT INTO anlage (anlage_id) VALUES (?) ON CONFLICT(anlage_id) DO NOTHING",
                (anlage_id,),
            )
            self._verbindung.commit()
        except Exception:
            self._verbindung.rollback()
            self._verbindung.close()
            raise

    def _initialisiere_schema(self) -> None:
        """Legt das normalisierte Ziel-Schema innerhalb einer Transaktion an."""
        self._verbindung.execute(
            "CREATE TABLE IF NOT EXISTS anlage ("
            "anlage_id TEXT PRIMARY KEY, name TEXT, hersteller TEXT, modell TEXT)"
        )
        messwert_felder = ", ".join(f'"{name}" {typ}' for name, typ in _FELD_TYPEN.items())
        self._verbindung.execute(
            "CREATE TABLE IF NOT EXISTS messwert ("
            "anlage_id TEXT NOT NULL, zeit_ns INTEGER NOT NULL, "
            f"{messwert_felder}, rohfelder_json TEXT, "
            "PRIMARY KEY (anlage_id, zeit_ns), "
            "FOREIGN KEY (anlage_id) REFERENCES anlage(anlage_id))"
        )
        self._verbindung.execute(
            "CREATE TABLE IF NOT EXISTS raum_messwert ("
            "anlage_id TEXT NOT NULL, zeit_ns INTEGER NOT NULL, "
            "raum_name TEXT NOT NULL, raum_c REAL, soll_c REAL, "
            "PRIMARY KEY (anlage_id, zeit_ns, raum_name), "
            "FOREIGN KEY (anlage_id, zeit_ns) "
            "REFERENCES messwert(anlage_id, zeit_ns) ON DELETE CASCADE)"
        )
        self._verbindung.execute(
            "CREATE TABLE IF NOT EXISTS stoerung ("
            "ereignis_id TEXT PRIMARY KEY, anlage_id TEXT NOT NULL, "
            "beginn_ns INTEGER NOT NULL, ende_ns INTEGER, fehlercode TEXT, "
            "beschreibung_roh TEXT, quelle TEXT, "
            "FOREIGN KEY (anlage_id) REFERENCES anlage(anlage_id))"
        )
        self._verbindung.execute(
            "CREATE TABLE IF NOT EXISTS wartung_reparatur ("
            "ereignis_id TEXT PRIMARY KEY, anlage_id TEXT NOT NULL, zeit_ns INTEGER NOT NULL, "
            "komponente TEXT, massnahme TEXT NOT NULL, bestaetigter_fehler TEXT, quelle TEXT, "
            "FOREIGN KEY (anlage_id) REFERENCES anlage(anlage_id))"
        )

    def _migriere_altes_schema(self) -> None:
        """Migriert JSON-Zeilen und Spaltenmetadaten atomar in das Zielschema."""
        tabellen = {
            zeile[0]
            for zeile in self._verbindung.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        alte_metadaten = "metadaten" in tabellen and "anlage_id" not in {
            zeile[1] for zeile in self._verbindung.execute("PRAGMA table_info(metadaten)")
        }
        if alte_metadaten:
            self._verbindung.execute("ALTER TABLE metadaten RENAME TO metadaten_alt")
        self._verbindung.execute(
            "CREATE TABLE IF NOT EXISTS metadaten ("
            "anlage_id TEXT NOT NULL, schluessel TEXT NOT NULL, wert TEXT NOT NULL, "
            "PRIMARY KEY (anlage_id, schluessel), "
            "FOREIGN KEY (anlage_id) REFERENCES anlage(anlage_id))"
        )

        if alte_metadaten:
            self._verbindung.execute(
                "INSERT INTO anlage (anlage_id) VALUES ('standard') "
                "ON CONFLICT(anlage_id) DO NOTHING"
            )
            self._verbindung.execute(
                "INSERT INTO metadaten (anlage_id, schluessel, wert) "
                "SELECT 'standard', schluessel, wert FROM metadaten_alt"
            )
            self._verbindung.execute("DROP TABLE metadaten_alt")

        if "messwerte" in tabellen:
            alte_spalten = {
                zeile[1] for zeile in self._verbindung.execute("PRAGMA table_info(messwerte)")
            }
            if {"zeit_ns", "daten"}.issubset(alte_spalten):
                self._verbindung.execute(
                    "INSERT INTO anlage (anlage_id) VALUES ('standard') "
                    "ON CONFLICT(anlage_id) DO NOTHING"
                )
                alte_zeilen = self._verbindung.execute(
                    "SELECT zeit_ns, daten FROM messwerte ORDER BY zeit_ns"
                ).fetchall()
                for zeit_ns, daten in alte_zeilen:
                    datensatz = json.loads(daten)
                    self._speichere_spalten(list(datensatz), "standard")
                    self._speichere_zeile(int(zeit_ns), datensatz, None, "standard")
                self._verbindung.execute("DROP TABLE messwerte")

    def speichern(
        self,
        df: pd.DataFrame,
        raum_soll_c: dict[str, float] | None = None,
    ) -> None:
        """Speichert DataFrame-Zeilen; Raumspalten werden relational abgelegt.

        Naive Zeitstempel werden als UTC interpretiert. ``raum_soll_c`` ist
        optional und ordnet Raumname einem dokumentierten Sollwert in °C zu.
        """
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
        spalten = list(df.columns)
        raum_soll_c = raum_soll_c or {}

        with self._verbindung:
            self._speichere_spalten(spalten)
            for zeit_ns, (_, zeile) in zip(zeiten_ns, df.iterrows(), strict=True):
                self._speichere_zeile(
                    int(zeit_ns),
                    {spalte: _json_wert(zeile[spalte]) for spalte in spalten},
                    raum_soll_c,
                )

    def _speichere_zeile(
        self,
        zeit_ns: int,
        datensatz: dict[str, object],
        raum_soll_c: dict[str, float] | None,
        anlage_id: str | None = None,
    ) -> None:
        """Schreibt eine einzelne Messung und ihre Raumwerte."""
        anlage_id = anlage_id or self.anlage_id
        raumwerte: dict[str, object] = {}
        rohfelder: dict[str, object] = {}
        typwerte: dict[str, object] = {}
        for feld, wert in datensatz.items():
            raum_match = _RAUM_SPALTE.fullmatch(feld)
            if raum_match:
                raumwerte[raum_match.group(1)] = wert
            elif feld in _FELD_TYPEN:
                typwerte[feld] = _sql_wert(feld, wert)
            else:
                rohfelder[feld] = _json_wert(wert)

        felder = ["anlage_id", "zeit_ns", *_FELD_TYPEN.keys(), "rohfelder_json"]
        werte = [
            anlage_id,
            zeit_ns,
            *(typwerte.get(feld) for feld in _FELD_TYPEN),
            json.dumps(rohfelder, ensure_ascii=False, allow_nan=False) if rohfelder else None,
        ]
        placeholders = ", ".join("?" for _ in felder)
        aktualisierung = ", ".join(
            f'"{feld}" = excluded."{feld}"' for feld in (*_FELD_TYPEN, "rohfelder_json")
        )
        self._verbindung.execute(
            f"INSERT INTO messwert ({', '.join(felder)}) VALUES ({placeholders}) "
            f"ON CONFLICT(anlage_id, zeit_ns) DO UPDATE SET {aktualisierung}",
            werte,
        )
        self._verbindung.execute(
            "DELETE FROM raum_messwert WHERE anlage_id = ? AND zeit_ns = ?",
            (anlage_id, zeit_ns),
        )
        for raum, temperatur in raumwerte.items():
            self._verbindung.execute(
                "INSERT INTO raum_messwert "
                "(anlage_id, zeit_ns, raum_name, raum_c, soll_c) VALUES (?, ?, ?, ?, ?)",
                (
                    anlage_id,
                    zeit_ns,
                    raum,
                    _sql_wert("raum_c", temperatur),
                    _sql_wert("soll_c", (raum_soll_c or {}).get(raum)),
                ),
            )

    def _speichere_spalten(self, spalten: list[str], anlage_id: str | None = None) -> None:
        anlage_id = anlage_id or self.anlage_id
        metadaten = self._verbindung.execute(
            "SELECT wert FROM metadaten WHERE anlage_id = ? AND schluessel = 'spalten'",
            (anlage_id,),
        ).fetchone()
        bekannte_spalten = json.loads(metadaten[0]) if metadaten else []
        bekannte_spalten.extend(spalte for spalte in spalten if spalte not in bekannte_spalten)
        self._verbindung.execute(
            "INSERT INTO metadaten (anlage_id, schluessel, wert) VALUES (?, 'spalten', ?) "
            "ON CONFLICT(anlage_id, schluessel) DO UPDATE SET wert = excluded.wert",
            (anlage_id, json.dumps(bekannte_spalten, ensure_ascii=False)),
        )

    def lese(self, von: datetime, bis: datetime) -> pd.DataFrame:
        """Lädt Messwerte im halboffenen Zeitraum ``[von, bis)``."""
        von_ns = self._zeit_ns(von)
        bis_ns = self._zeit_ns(bis)
        zeilen = self._verbindung.execute(
            "SELECT zeit_ns, " + ", ".join(f'"{feld}"' for feld in _FELD_TYPEN)
            + ", rohfelder_json FROM messwert "
            "WHERE anlage_id = ? AND zeit_ns >= ? AND zeit_ns < ? ORDER BY zeit_ns",
            (self.anlage_id, von_ns, bis_ns),
        ).fetchall()
        metadaten = self._verbindung.execute(
            "SELECT wert FROM metadaten WHERE anlage_id = ? AND schluessel = 'spalten'",
            (self.anlage_id,),
        ).fetchone()
        spalten = json.loads(metadaten[0]) if metadaten else []
        raumzeilen = self._verbindung.execute(
            "SELECT zeit_ns, raum_name, raum_c FROM raum_messwert "
            "WHERE anlage_id = ? AND zeit_ns >= ? AND zeit_ns < ?",
            (self.anlage_id, von_ns, bis_ns),
        ).fetchall()
        raumwerte: dict[int, dict[str, object]] = {}
        for zeit_ns, raum, temperatur in raumzeilen:
            raumwerte.setdefault(zeit_ns, {})[f"raum_{raum}_c"] = temperatur

        datensaetze = []
        for zeile in zeilen:
            zeit_ns, *werte, rohfelder_json = zeile
            datensatz = dict(zip(_FELD_TYPEN, werte, strict=True))
            for feld in _BOOLEAN_FELDER:
                if datensatz[feld] is not None:
                    datensatz[feld] = bool(datensatz[feld])
            if rohfelder_json:
                datensatz.update(json.loads(rohfelder_json))
            datensatz.update(raumwerte.get(zeit_ns, {}))
            datensaetze.append(datensatz)

        index = pd.to_datetime([zeile[0] for zeile in zeilen], unit="ns", utc=True)
        return pd.DataFrame.from_records(datensaetze, columns=spalten, index=None).set_axis(index)

    def lese_raum_messwerte(self, von: datetime, bis: datetime) -> pd.DataFrame:
        """Liefert normalisierte Raumtemperatur- und Sollwertzeilen im Zeitraum."""
        zeilen = self._verbindung.execute(
            "SELECT zeit_ns, raum_name, raum_c, soll_c FROM raum_messwert "
            "WHERE anlage_id = ? AND zeit_ns >= ? AND zeit_ns < ? "
            "ORDER BY zeit_ns, raum_name",
            (self.anlage_id, self._zeit_ns(von), self._zeit_ns(bis)),
        ).fetchall()
        df = pd.DataFrame.from_records(
            [(raum, temperatur, soll) for _, raum, temperatur, soll in zeilen],
            columns=["raum_name", "raum_c", "soll_c"],
        )
        df.index = pd.to_datetime([zeit_ns for zeit_ns, *_ in zeilen], unit="ns", utc=True)
        return df

    def speichern_stoerung(self, stoerung: Stoerung) -> None:
        """Speichert oder aktualisiert einen unveränderten Störungseintrag."""
        with self._verbindung:
            self._speichere_ereignis(
                "stoerung",
                stoerung.ereignis_id,
                (
                    self.anlage_id,
                    self._zeit_ns(stoerung.beginn),
                    self._zeit_ns(stoerung.ende) if stoerung.ende is not None else None,
                    stoerung.fehlercode,
                    stoerung.beschreibung_roh,
                    stoerung.quelle,
                ),
                "beginn_ns, ende_ns, fehlercode, beschreibung_roh, quelle",
            )

    def lese_stoerungen(self, von: datetime, bis: datetime) -> list[Stoerung]:
        """Liest Störungen anhand ihres Beginns im halboffenen Zeitraum."""
        zeilen = self._verbindung.execute(
            "SELECT ereignis_id, beginn_ns, ende_ns, fehlercode, beschreibung_roh, quelle "
            "FROM stoerung WHERE anlage_id = ? AND beginn_ns >= ? AND beginn_ns < ? "
            "ORDER BY beginn_ns, ereignis_id",
            (self.anlage_id, self._zeit_ns(von), self._zeit_ns(bis)),
        ).fetchall()
        return [
            Stoerung(
                ereignis_id,
                _datetime_utc(beginn),
                _datetime_utc(ende) if ende is not None else None,
                fehlercode,
                beschreibung,
                quelle,
            )
            for ereignis_id, beginn, ende, fehlercode, beschreibung, quelle in zeilen
        ]

    def speichern_wartung_reparatur(self, ereignis: WartungReparatur) -> None:
        """Speichert oder aktualisiert einen dokumentierten Wartungseintrag."""
        with self._verbindung:
            self._speichere_ereignis(
                "wartung_reparatur",
                ereignis.ereignis_id,
                (
                    self.anlage_id,
                    self._zeit_ns(ereignis.zeit),
                    ereignis.komponente,
                    ereignis.massnahme,
                    ereignis.bestaetigter_fehler,
                    ereignis.quelle,
                ),
                "zeit_ns, komponente, massnahme, bestaetigter_fehler, quelle",
            )

    def lese_wartung_reparaturen(
        self, von: datetime, bis: datetime
    ) -> list[WartungReparatur]:
        """Liest Wartungs- und Reparatureinträge im halboffenen Zeitraum."""
        zeilen = self._verbindung.execute(
            "SELECT ereignis_id, zeit_ns, komponente, massnahme, bestaetigter_fehler, quelle "
            "FROM wartung_reparatur WHERE anlage_id = ? AND zeit_ns >= ? AND zeit_ns < ? "
            "ORDER BY zeit_ns, ereignis_id",
            (self.anlage_id, self._zeit_ns(von), self._zeit_ns(bis)),
        ).fetchall()
        return [
            WartungReparatur(
                ereignis_id,
                _datetime_utc(zeit_ns),
                massnahme,
                komponente,
                bestaetigter_fehler,
                quelle,
            )
            for ereignis_id, zeit_ns, komponente, massnahme, bestaetigter_fehler, quelle in zeilen
        ]

    def _speichere_ereignis(
        self,
        tabelle: str,
        ereignis_id: str,
        werte: tuple[object, ...],
        aktualisierungsfelder: str,
    ) -> None:
        """Führt ein Upsert für eine Ereignis-ID aus, ohne sie zwischen Anlagen zu verschieben."""
        feldnamen = (
            "anlage_id, "
            + ("beginn_ns, ende_ns, fehlercode, beschreibung_roh, quelle"
               if tabelle == "stoerung"
               else "zeit_ns, komponente, massnahme, bestaetigter_fehler, quelle")
        )
        self._verbindung.execute(
            f"INSERT INTO {tabelle} (ereignis_id, {feldnamen}) VALUES "
            f"({', '.join('?' for _ in range(len(werte) + 1))}) "
            f"ON CONFLICT(ereignis_id) DO UPDATE SET "
            f"{', '.join(f'{feld} = excluded.{feld}' for feld in aktualisierungsfelder.split(', '))} "
            "WHERE anlage_id = excluded.anlage_id",
            (ereignis_id, *werte),
        )
        gespeicherte_anlage = self._verbindung.execute(
            f"SELECT anlage_id FROM {tabelle} WHERE ereignis_id = ?", (ereignis_id,)
        ).fetchone()
        if gespeicherte_anlage and gespeicherte_anlage[0] != self.anlage_id:
            raise ValueError(f"Die Ereignis-ID {ereignis_id!r} gehört bereits zu einer anderen Anlage.")

    @staticmethod
    def _zeit_ns(zeit: datetime) -> int:
        """Konvertiert einen Zeitpunkt in UTC-Nanosekunden seit der Epoche."""
        zeitstempel = pd.Timestamp(zeit)
        if zeitstempel.tz is None:
            zeitstempel = zeitstempel.tz_localize("UTC")
        else:
            zeitstempel = zeitstempel.tz_convert("UTC")
        return zeitstempel.value

    def close(self) -> None:
        """Schließt die SQLite-Verbindung."""
        self._verbindung.close()

    def __enter__(self) -> Self:
        """Gibt den Speicher für eine ``with``-Anweisung zurück."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Schließt die Verbindung beim Verlassen einer ``with``-Anweisung."""
        self.close()


def _fehlend(wert: object) -> bool:
    """Prüft skalare pandas-/Python-Fehlwerte ohne Arrays mehrdeutig auszuwerten."""
    if wert is None:
        return True
    fehlend = pd.isna(wert)
    return bool(fehlend) if isinstance(fehlend, bool) else False


def _json_wert(wert: object) -> object:
    """Wandelt skalare pandas- und NumPy-Werte in JSON-kompatible Werte um."""
    if _fehlend(wert):
        return None
    if isinstance(wert, dict):
        return {str(schluessel): _json_wert(element) for schluessel, element in wert.items()}
    if isinstance(wert, (list, tuple)):
        return [_json_wert(element) for element in wert]
    if hasattr(wert, "item") and callable(wert.item):
        wert = wert.item()
    if isinstance(wert, pd.Timestamp):
        return wert.isoformat()
    if isinstance(wert, datetime):
        return wert.isoformat()
    if isinstance(wert, float) and not math.isfinite(wert):
        return None
    return wert


def _sql_wert(feld: str, wert: object) -> object:
    """Konvertiert einen typisierten Wert passend zum dokumentierten SQLite-Feld."""
    wert = _json_wert(wert)
    if wert is None:
        return None
    if feld in _BOOLEAN_FELDER:
        return int(bool(wert))
    if feld in _INTEGER_FELDER:
        return int(wert)
    if feld in _FELD_TYPEN and _FELD_TYPEN[feld] == "REAL" or feld in {"raum_c", "soll_c"}:
        return float(wert)
    return str(wert) if feld in _FELD_TYPEN and _FELD_TYPEN[feld] == "TEXT" else wert


def _datetime_utc(zeit_ns: int) -> datetime:
    """Konvertiert UTC-Nanosekunden in einen zeitzonenbewussten Python-Zeitpunkt."""
    return pd.Timestamp(zeit_ns, unit="ns", tz="UTC").to_pydatetime()
