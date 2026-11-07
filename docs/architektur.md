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
| `adapters/base.py`, `adapters/csv_adapter.py` | datensammler | generischer CSV-Adapter vorhanden; fokussiertes Luxtronik-CSV-Mapping offen |
| `adapters/luxtronik.py` | datensammler | vorhanden (nur lesend, Live) |
| `adapters/novelan_ladv9.py` | datensammler | vorhanden (Home-Assistant-REST-API) |
| `monitor.py` | datensammler | vorhanden (60-s-Abfrage nach SQLite) |
| `ha_monitor.py` | datensammler | vorhanden (Home-Assistant-Adapter und SQLite) |
| `run.py` | architekt | vorhanden (Sammeln, Regelprüfung und Tagesbericht im Scheduler) |
| `testseite.py` | datensammler | vorhanden (manuelle Testabfrage) |
| `wp-analyse/` | datensammler | Supervisor-App-Konfiguration und Dockerfile vorhanden; Installation, Image-Build und Laufzeit nicht verifiziert |
| `analyse/taktung.py` | analyst | Beispiel vorhanden |
| `analyse/verdichter.py` | analyst | vorhanden (Richtwerte, Herstellerwerte offen) |
| `analyse/spreizung.py`, `effizienz.py`, `komfort.py` | analyst | vorhanden; Grenzen und Tests siehe `backlog.md` |
| `speicher/sqlite.py` | datensammler | relationales Zielschema und Migration im Code; vorhandene Live-DB noch im Altschema |
| `erfassung.py`, `monitoring.py`, `tageslauf.py` | datensammler / alarm / analyst | Orchestrierungsfunktionen vorhanden; integrierter Scheduler/CLI `run.py` offen |
| `alarm/` | alarm | AlarmManager und ntfy vorhanden; Telegram und Laufzeitverdrahtung fehlen |
| `bericht/tagesbericht.py` | analyst | vorhanden |
| `dashboard.py` | Streamlit-Dashboard | vorhanden (Live und Simulation) |

Die Statusangaben beziehen sich auf Code im Repository und die unten aufgeführte
Live-Verifikation, nicht auf einen validierten Dauerbetrieb. Tests mit Fakes belegen
keine reale Verbindung zum Regler oder zu Home Assistant.

## Test- und CI-Konzept

### Testebenen
- **Unit-Tests:** reine Analysefunktionen und Datenverarbeitung mit kleinen, synthetischen
  DataFrames. Grenzwerte, fehlende Werte und nicht auswertbare Kennzahlen werden explizit geprüft.
- **Adapter- und Simulationstests:** synthetische oder gemockte Antworten prüfen Feldmapping,
  UTC-Zeitstempel und Fehlerbehandlung. Sie belegen keinen Zugriff auf reale Geräte.
- **Integrations-Tests:** Speicher- und Ablaufpfade verwenden temporäre SQLite-Datenbanken sowie
  Fake-Adapter, Fake-Melder und kontrollierte Eingaben; kein echter Netzwerkzugriff.
- **Manuelle Live-Prüfungen:** Regler, Home Assistant und App-Laufzeit bleiben separat zu
  verifizieren und sind kein Bestandteil der CI.

Neue Funktionen erhalten Tests mit synthetischen Daten; externe Systeme und Zugangsdaten sind
für die Tests nicht erforderlich. Die Tests sollen reproduzierbar, zeitunabhängig und ohne
Wartezeiten laufen. Der lokale Qualitätslauf besteht aus `ruff check .` und `pytest`.

### CI-/Build-Abgrenzung

Der Workflow [`quality-checks.yaml`](../.github/workflows/quality-checks.yaml) führt bei
jedem Pull Request und bei Pushes auf `main` den Job „Python quality checks“ mit Python 3.11
aus. Er installiert das Projekt samt Entwicklungsabhängigkeiten mit
`python -m pip install -e ".[dev]"` und führt `ruff check .` sowie `pytest` aus. Die lokalen
Prüfungen entsprechen den CI-Kommandos; nach der Installation sind sie mit `ruff check .`
und `pytest` ausführbar.

Der Workflow [`build-app.yaml`](../.github/workflows/build-app.yaml) bleibt getrennt und
baut beziehungsweise veröffentlicht das Home-Assistant-Image. Weder der Qualitätsworkflow
noch der Image-Build benötigen für diese Prüfungen Live-Zugangsdaten oder Zugriffe auf
Wärmepumpen und Home Assistant. Tests mit Fakes und synthetischen Daten belegen keine reale
Geräteverbindung; Live- und Deployment-Prüfungen bleiben manuell.

Damit die Qualitätschecks ein Merge-Gate sind, muss die Repository-Administration den
Statuscheck des Jobs in den Branch-Protection- beziehungsweise Ruleset-Einstellungen für
`main` als erforderlich aktivieren. Ein erfolgreicher Image-Build allein weist nicht nach,
dass Ruff und pytest erfolgreich waren.

## Live-Datenfluss
```
 Luxtronik-Regler ──(TCP 8889, lesend)──► LuxtronikAdapter.aktuell()
        ▼
 Monitor (≥ 60 s) ──► SQLiteSpeicher (data/wp.sqlite) ──► dashboard.py / analyse/
```
Der Regler hat keine Historie; Daten entstehen nur, solange Monitor oder Dashboard laufen.
Das Dashboard fragt nur ab, wenn die letzte Messung älter als das Intervall ist.
Siehe [`luxtronik-anbindung.md`](luxtronik-anbindung.md).

## Integrierter Dauerbetrieb

`python -m wpanalyse.run` verbindet `sammle_und_speichere`, `pruefe_und_melde` und
`erzeuge_tagesbericht`. Der Lauf nutzt den `NovelanLadv9Adapter` und benötigt daher
`HA_URL`, `HA_TOKEN` und mindestens eine konfigurierte `NOVELAN_ENTITY_*`-Variable.
Das Sammelintervall wird in Sekunden über `--intervall` oder `WPANALYSE_INTERVAL`
gesetzt (Standard: 60); Datenbank und Berichtsziel sind über `--db` /
`WPANALYSE_DB` und `--bericht-ordner` / `WPANALYSE_REPORT_DIR` konfigurierbar.
Die Regeln werden beim Start und anschließend alle 15 Minuten über die letzten
31 Tage geprüft. An jedem UTC-Tageswechsel wird der Bericht des abgeschlossenen
Vortags unter `<Berichtsziel>/JJJJ-MM-TT.md` gespeichert.

Mit `NTFY_TOPIC` werden Alarme über ntfy versendet; ohne ntfy-Konfiguration werden
Befunde protokolliert. Sammel-, Prüf- oder Berichtsfehler beenden den Prozess mit
Fehlerstatus, statt den fehlgeschlagenen Lauf als erfolgreich zu behandeln. Strg+C
und SIGTERM beenden den Scheduler geordnet. Die Regelprüfung und Berichtserzeugung
arbeiten mit den gespeicherten Werten; die Tagesberichte verwenden UTC.

Die am 07.11.2026 geprüfte `data/wp.sqlite` enthielt 58 Messungen, bestand die
SQLite-Integritätsprüfung und wies 5 Abstände von mehr als 90 Sekunden auf. Sie enthält
noch das Altschema `messwerte(zeit_ns, daten)` statt des relationalen Zielschemas.
**Vor dem ersten Öffnen dieser Datei mit dem aktuellen `SQLiteSpeicher` sichern**: Die
Schema-Migration wird beim Initialisieren automatisch ausgeführt.
Der Live-Reglerzugriff über das Streamlit-Dashboard wurde am selben Tag erfolgreich
geprüft; Dauerbetrieb ist nicht validiert.

## Home-Assistant-App

```
Wärmepumpe → Home-Assistant-Integration → HA-Entitäten / REST-API
          → NovelanLadv9Adapter → ha_monitor.py → SQLiteSpeicher (/data/wp.sqlite)
```

`python -m wpanalyse.ha_monitor` startet den eigenständigen Monitor. Das Repository
enthält die Supervisor-App unter `wp-analyse/`, deren Einstieg `ha_monitor.py` mit
Supervisor-Optionen startet. Der lokale amd64-Container-Build war laut
[`home-assistant-betrieb.md`](home-assistant-betrieb.md) erfolgreich; Installation und
tatsächlicher Start auf Home Assistant OS wurden nicht verifiziert. Die App-Konfiguration
legt `/data/wp.sqlite` als Datenbankpfad fest; ob dieses Verzeichnis im Zielsystem
dauerhaft gesichert wird, hängt von der jeweiligen Installation ab. Der App-Build ist
für `aarch64` und `amd64` konfiguriert; der aarch64-Build wurde nicht nachgewiesen.
`armv7`/32-Bit ist nicht freigegeben. Ein nativer Home-Assistant-Integration- oder
Dashboard-Export ist nicht enthalten.

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
Die geplante Luxtronik-CSV-Zuordnung umfasst `aussen_c`, `vorlauf_c`, `ruecklauf_c`,
`verdichter_an`, `heizstab_an`, `betriebsart` und `verdichter_starts_zaehler`; die namenlose
erste Spalte ist der Zeitstempel. Der generische `CsvAdapter` setzt derzeit eine benannte
Zeitspalte voraus und implementiert diese Feldzuordnung noch nicht. `waerme_w` bleibt
Wärmeleistung. Im vorliegenden Export gibt es keine bestätigte elektrische Leistung oder
elektrische Energie, daher sind `leistung_w`, `strom_kwh` und `waerme_kwh` aus diesem Export
nicht belegbar und die Arbeitszahl nicht berechenbar. `lux_ID_WEB_WMZ_*`,
Laufzeit-/Abtauungswerte und `ERROR_Nr0–4` werden erst nach Prüfung ihrer Bedeutung und Einheit
zugeordnet.

Der aktuelle `SQLiteSpeicher` verwendet das relationale Zielschema und migriert das frühere
`messwerte(zeit_ns, daten)`-Format beim Öffnen unter der Standard-Anlagen-ID. Diese Migration
ist im Code implementiert; ein Migrationstest mit synthetischen Testdaten ist vorhanden,
wurde hier mangels pytest in der Projektumgebung aber nicht ausgeführt. Die am 07.11.2026 vorhandene `data/wp.sqlite` liegt
jedoch noch im alten Format; sie wurde nicht migriert. Vor ihrer ersten Öffnung mit dem
aktuellen Speicher ist eine Sicherung erforderlich.
