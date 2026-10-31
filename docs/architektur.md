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
 bericht/       → Tages-/Wochenbericht, später Dashboard (Streamlit oder Grafana)
```

## Module
| Modul | Zuständiger Agent | Status |
|---|---|---|
| `models.py` | architekt | vorhanden |
| `config.py` | architekt | vorhanden |
| `simulation.py` | tester | Grundversion |
| `adapters/base.py`, `adapters/csv_adapter.py` | datensammler | vorhanden |
| `analyse/taktung.py` | analyst | Beispiel vorhanden |
| `analyse/*` (weitere) | analyst | offen |
| `speicher/` | datensammler | offen |
| `alarm/` | alarm | offen |
| `bericht/` | analyst | offen |

## Datenformat
Ein pandas-DataFrame mit `DatetimeIndex` (UTC), eine Spalte je Feld aus `docs/fachwissen.md`.
Fehlende Werte = `NaN`. Abtastrate typisch 1 Minute.
