# WP-Analyse – Wärmepumpen-Monitoring mit KI-Agenten

Lernprojekt: eine Anwendung, die den Betrieb einer Wärmepumpe analysiert und Anomalien meldet –
entwickelt mit **mehreren GitHub-Copilot-Agenten**.

## Ziele der App
1. **Bewertung**: Läuft die WP effizient (Arbeitszahl), schonend (Taktung, Heizstab) und ist es überall warm genug?
2. **Monitoring**: Auffälligkeiten und mögliche Fehler frühzeitig erkennen und melden.

## Schnellstart
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m wpanalyse.demo          # erzeugt Testdaten und zeigt erste Kennzahlen
pytest
```
Die App läuft zuerst mit **simulierten Daten**. Die echte Wärmepumpe wird später über einen Adapter angebunden
(Home Assistant, Hersteller-API oder Modbus) – siehe `docs/backlog.md`, Issue 2.

## Aufbau
| Ordner | Inhalt |
|---|---|
| `.github/copilot-instructions.md` | Regeln, die **jeder** Agent befolgt |
| `.github/agents/` | Spezialisierte Agenten (Architekt, Datensammler, Analyst, Alarm, Tester, Reviewer) |
| `docs/lernpfad.md` | **Hier anfangen**: Schritt-für-Schritt lernen, mit Agenten zu arbeiten |
| `docs/architektur.md` | Datenfluss und Module |
| `docs/fachwissen.md` | Kennzahlen und Anomalie-Regeln für Wärmepumpen |
| `docs/backlog.md` | Fertige Issues zum Verteilen an Agenten |
| `src/wpanalyse/` | Code-Gerüst (Datenmodell, Adapter, erste Analyse) |
