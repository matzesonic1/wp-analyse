# Projektregeln für alle Copilot-Agenten

## Projekt
WP-Analyse: Python-Anwendung, die Messdaten einer Wärmepumpe (WP) sammelt, Kennzahlen berechnet
und Anomalien meldet. Fachwissen steht in `docs/fachwissen.md` – lies es, bevor du Analyse-Logik schreibst.

**Projektwurzel:** Repository-Root

## Technik
- Python 3.11+, Abhängigkeiten in `pyproject.toml`. Datenanalyse mit `pandas`.
- Code liegt in `src/wpanalyse/`, Tests in `tests/` (pytest).
- Alle Messwerte laufen durch das Datenmodell `Messwert` in `src/wpanalyse/models.py`.
- Neue Datenquellen implementieren `DatenAdapter` aus `src/wpanalyse/adapters/base.py`.
- Analysen sind reine Funktionen: DataFrame rein, Ergebnis (Dataclass) raus. Kein I/O in `src/wpanalyse/analyse/`.

## Regeln
- Einheiten immer im Namen: `vorlauf_c`, `leistung_w`, `energie_kwh`.
- Schwellwerte nie hart im Code, sondern in `src/wpanalyse/config.py`.
- Zu jeder neuen Funktion gehört ein Test mit synthetischen Daten (`src/wpanalyse/simulation.py`).
- Keine Zugangsdaten im Code – nur über Umgebungsvariablen (`.env`, nicht committen).
- Code-Kommentare und Docstrings auf Deutsch, Bezeichner auf Deutsch ohne Umlaute.
- Vor dem Abschluss: `pytest` und `ruff check .` müssen grün sein.

## Arbeitsweise
- Bearbeite nur die Dateien, die dein Issue betrifft. Ändere keine Schnittstellen anderer Module ohne Hinweis im PR.
- Beschreibe im PR: was, warum, wie getestet.
