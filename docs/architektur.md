# Architektur

```
 Wärmepumpe / Sensoren
        │  (Home Assistant · Hersteller-API · Modbus · CSV)
        ▼
 adapters/      → liest Rohdaten, wandelt in Messwert um
        ▼
 speicher/      → SQLite (später optional InfluxDB)
        ▼
 analyse/       → Kennzahlen + Anomalie-Regeln  (reine Funktionen)
        ▼
 alarm/         → entscheidet & versendet Meldungen (Telegram, E-Mail, ntfy)
 dashboard.py   → Streamlit-Dashboard für Messwertverläufe und Kennzahlen
```

## Module
| Modul | Zuständiger Agent | Status |
|---|---|---|
| `models.py` | architekt | vorhanden |
| `config.py` | architekt | vorhanden |
| `simulation.py` | tester | Grundversion |
| `adapters/base.py`, `adapters/csv_adapter.py` | datensammler | vorhanden |
| `adapters/luxtronik.py` | datensammler | vorhanden (nur lesend, Live) |
| `monitor.py` | datensammler | vorhanden (60-s-Abfrage nach SQLite) |
| `testseite.py` | datensammler | vorhanden (manuelle Testabfrage) |
| `analyse/taktung.py` | analyst | Beispiel vorhanden |
| `analyse/verdichter.py` | analyst | vorhanden (Richtwerte, Herstellerwerte offen) |
| `analyse/*` (weitere) | analyst | offen |
| `speicher/sqlite.py` | datensammler | SQLite-Speicher vorhanden (JSON-Zeilenformat; relationales Zielschema offen) |
| `alarm/` | alarm | offen |
| `bericht/tagesbericht.py` | analyst | vorhanden |
| `dashboard.py` | Streamlit-Dashboard | vorhanden (Live und Simulation) |

## Live-Datenfluss
```
 Luxtronik-Regler ──(TCP 8889, lesend)──► LuxtronikAdapter.aktuell()
        ▼
 Monitor (≥ 60 s) ──► SQLiteSpeicher (data/wp.sqlite) ──► dashboard.py / analyse/
```
Der Regler hat keine Historie; Daten entstehen nur, solange Monitor oder Dashboard laufen.
Das Dashboard fragt nur ab, wenn die letzte Messung älter als das Intervall ist.
Siehe [`luxtronik-anbindung.md`](luxtronik-anbindung.md).

## Datenformat
Ein pandas-DataFrame mit `DatetimeIndex` (UTC), eine Spalte je Feld aus `docs/fachwissen.md`.
Fehlende Werte = `NaN`. Abtastrate typisch 1 Minute.

## Datenbankschema (Ziel)
Die SQLite-Datenbank speichert Messwerte pro Anlage und Zeitpunkt. Alle Messzeitpunkte werden
als UTC-Nanosekunden (`INTEGER`) gespeichert. Pflichtfelder sind nur `anlage.anlage_id`,
`messwert.anlage_id` und `messwert.zeit_ns`; nicht verfügbare Messwerte bleiben `NULL`.
SQLite-Fremdschlüsselprüfungen sind für jede Verbindung aktiviert.
Der zusammengesetzte Schlüssel `(anlage_id, zeit_ns)` erlaubt mehrere Anlagen und verhindert
doppelte Messzeilen für denselben Zeitpunkt einer Anlage.

### `anlage`
| Spalte | SQLite-Typ | NULL? | Bedeutung |
|---|---|---:|---|
| `anlage_id` | `TEXT PRIMARY KEY` | nein | Vom Betreiber vergebene, stabile Anlagen-ID |
| `name` | `TEXT` | ja | Anzeigename |
| `hersteller` | `TEXT` | ja | Hersteller, falls bekannt |
| `modell` | `TEXT` | ja | Modell, falls bekannt |

### `messwert`
| Spalte | SQLite-Typ | NULL? | Bedeutung |
|---|---|---:|---|
| `anlage_id` | `TEXT` | nein | Fremdschlüssel auf `anlage.anlage_id` |
| `zeit_ns` | `INTEGER` | nein | Messzeitpunkt als UTC-Nanosekunden seit Epoche |
| `aussen_c` | `REAL` | ja | Außentemperatur in °C |
| `vorlauf_c` | `REAL` | ja | Vorlauftemperatur in °C |
| `ruecklauf_c` | `REAL` | ja | Rücklauftemperatur in °C |
| `verdichter_an` | `INTEGER` | ja | Verdichterzustand (`0`/`1`) |
| `verdichter_hz` | `REAL` | ja | Verdichterfrequenz in Hz |
| `betriebsart` | `TEXT` | ja | Zum Beispiel `heizen`, `warmwasser`, `abtauen`, `aus` |
| `heizstab_an` | `INTEGER` | ja | Heizstabzustand (`0`/`1`) |
| `leistung_w` | `REAL` | ja | Elektrische Momentanleistung in W |
| `strom_kwh` | `REAL` | ja | Elektrische Energie des Messintervalls in kWh |
| `strom_zaehler_kwh` | `REAL` | ja | Bestätigter kumulativer Strom-Energiezählerstand in kWh |
| `waerme_w` | `REAL` | ja | Erzeugte Wärmeleistung in W |
| `waerme_kwh` | `REAL` | ja | Erzeugte Wärmeenergie des Messintervalls in kWh |
| `waerme_zaehler_kwh` | `REAL` | ja | Bestätigter kumulativer Wärme-Energiezählerstand in kWh |
| `verdichter_starts_zaehler` | `INTEGER` | ja | Kumulativer Startzählerstand, nicht Starts je Messzeile |
| `verdichter_betriebszeit_zaehler_s` | `REAL` | ja | Bestätigter kumulativer Betriebszeit-Zählerstand in Sekunden |
| `verdichter_laufzeit_intervall_s` | `REAL` | ja | Verdichterlaufzeit im Messintervall in Sekunden |
| `warmwasser_c` | `REAL` | ja | Warmwassertemperatur in °C |
| `ruecklauf_soll_c` | `REAL` | ja | Rücklauf-Solltemperatur in °C |
| `quelle` | `TEXT` | ja | Adapter oder Herkunft, zum Beispiel `luxtronik` oder `csv` |
| `rohfelder_json` | `TEXT` | ja | JSON-Objekt mit unverändert übernommenen, noch nicht zugeordneten Quellfeldern |

Primärschlüssel: `(anlage_id, zeit_ns)`; `anlage_id` ist Fremdschlüssel auf `anlage.anlage_id`.
`strom_kwh` und `waerme_kwh` bezeichnen ausschließlich Energie im Messintervall. Zählerstände
werden separat gespeichert und dürfen erst befüllt werden, wenn Einheit, Zählerverhalten und
Bilanzgrenze der Datenquelle bestätigt sind. Rohdatenfelder ohne bestätigte
Bedeutung gehören nicht in die typisierten Analysefelder; falls sie aufbewahrt werden, bleiben sie
als Schlüssel/Wert-Paare in `rohfelder_json` und sind für Analysen nicht automatisch verfügbar.

### `raum_messwert`
Eine Zeile pro Anlage, Zeitpunkt und Raum; Primärschlüssel `(anlage_id, zeit_ns, raum_name)`.
`anlage_id TEXT NOT NULL` verweist auf `anlage`, `zeit_ns INTEGER NOT NULL` ist UTC-Nanosekunde,
`raum_name TEXT NOT NULL` benennt den Raum, `raum_c REAL NULL` speichert die Temperatur in °C und
`soll_c REAL NULL` den zu diesem Zeitpunkt gültigen Sollwert in °C. Damit bleiben beliebig viele
Räume möglich, ohne Spalten dynamisch anzulegen.

### `stoerung` und `wartung_reparatur`
`stoerung` enthält `ereignis_id TEXT PRIMARY KEY`, `anlage_id TEXT NOT NULL`,
`beginn_ns INTEGER NOT NULL`, `ende_ns INTEGER NULL`, `fehlercode TEXT NULL`,
`beschreibung_roh TEXT NULL` und `quelle TEXT NULL`. Herstellerfehlercodes bleiben zunächst
unverändert; dekodierte Diagnosen benötigen eine separat geprüfte Code-Zuordnung.

`wartung_reparatur` enthält `ereignis_id TEXT PRIMARY KEY`, `anlage_id TEXT NOT NULL`,
`zeit_ns INTEGER NOT NULL`, `komponente TEXT NULL`, `massnahme TEXT NOT NULL`,
`bestaetigter_fehler TEXT NULL` und `quelle TEXT NULL`. Diese dokumentierten Ereignisse sind
später nötig, um Defektvorhersagen mit bestätigten Fällen statt bloßen Auffälligkeiten zu bewerten.

### Importzuordnung und Migration
Der Luxtronik-CSV-Export kann zunächst `aussen_c`, `vorlauf_c`, `ruecklauf_c`, `verdichter_an`,
`heizstab_an`, `betriebsart` und `verdichter_starts_zaehler` befüllen; die namenlose erste Spalte
ist der Zeitstempel. `waerme_w` bleibt Wärmeleistung. Im vorliegenden Export gibt es keine
bestätigte elektrische Leistung oder elektrische Energie, daher bleiben `leistung_w`,
`strom_kwh` und `waerme_kwh` leer und die Arbeitszahl nicht berechenbar. `lux_ID_WEB_WMZ_*`,
Laufzeit-/Abtauungswerte und `ERROR_Nr0–4` werden erst nach Prüfung ihrer Bedeutung und Einheit
zugeordnet.

Der aktuelle `SQLiteSpeicher` verwendet `messwerte(zeit_ns, daten)` mit JSON-Nutzdaten. Die
Umstellung auf Tabellen mit festen Spalten muss vorhandene Daten erhalten: bisherige Zeilen sind
unter einer dokumentierten Standard-Anlagen-ID zu migrieren. DataFrame-Schnittstelle,
UTC-Normalisierung, Zeitraumabfragen und Ersetzen desselben Zeitpunkts je Anlage bleiben erhalten.
