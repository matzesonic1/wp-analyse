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
| `speicher/` | datensammler | offen |
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
