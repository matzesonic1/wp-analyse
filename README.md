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

## Dashboard
```bash
pip install -e ".[dashboard]"
streamlit run src/wpanalyse/dashboard.py
```
Das Dashboard zeigt simulierte Temperatur- und Leistungsverläufe, Verdichterstarts pro Tag sowie die
Arbeitszahl in Abhängigkeit von der Außentemperatur.

## Aufbau
| Ordner | Inhalt |
|---|---|
| `.github/copilot-instructions.md` | Regeln, die **jeder** Agent befolgt |
| `.github/agents/` | In VS Code und GitHub auswählbare Agenten: Architekt, Datensammler, Analyst, Alarm, Tester und Reviewer |
| `docs/lernpfad.md` | **Hier anfangen**: Schritt-für-Schritt lernen, mit Agenten zu arbeiten |
| `docs/architektur.md` | Datenfluss und Module |
| `docs/fachwissen.md` | Kennzahlen und Anomalie-Regeln für Wärmepumpen |
| `docs/backlog.md` | Fertige Issues zum Verteilen an Agenten |
| `src/wpanalyse/` | Code-Gerüst (Datenmodell, Adapter, erste Analyse) |

## Agenten auswählen
Öffne in VS Code den Repository-Ordner als Workspace und wähle im Chat-Agenten-Auswahlmenü
einen Agenten wie **Analyst** oder **Tester**. Die Profile liegen unter `.github/agents/*.agent.md`.
Auf GitHub findest du sie im Repository im Tab **Agents**; nach Änderungen müssen die Profile
auf `main` liegen. Wähle dort den Agenten im Copilot-Auswahlmenü beim Prompt aus.
Die Dateien sind auch direkt unter
[`.github/agents/`](https://github.com/matzesonic1/wp-analyse/tree/main/.github/agents) einsehbar.
