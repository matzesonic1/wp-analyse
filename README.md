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
ruff check .
pytest
```
Der GitHub-Actions-Workflow `Quality checks` führt Ruff und pytest bei Pull Requests und
Pushes auf `main` aus. Er ist vom Home-Assistant-Image-Build getrennt und benötigt keine
Live-Geräte oder Zugangsdaten. Damit die Prüfungen Merge-Voraussetzung sind, muss der
Statuscheck in den Repository-Regeln für `main` als erforderlich aktiviert werden.
Die App läuft mit **simulierten Daten** oder mit **echten Messwerten** direkt vom
Luxtronik-Regler (Novelan/Alpha Innotec, nur lesend, alle 60 s). Details:
[`docs/luxtronik-anbindung.md`](docs/luxtronik-anbindung.md). Alternativ gibt es einen
Home-Assistant-Adapter: [`docs/novelan-ladv9-adapter.md`](docs/novelan-ladv9-adapter.md).
Das Konzept für den Betrieb auf Home Assistant OS steht in
[`docs/home-assistant-betrieb.md`](docs/home-assistant-betrieb.md).
Für den Dauerbetrieb mit Home Assistant:
`python -m wpanalyse.ha_monitor --intervall 60 --db data/wp.sqlite`.
Für den integrierten Ablauf aus Sammeln, Regelprüfung und täglichem UTC-Bericht:
`python -m wpanalyse.run --intervall 60 --db data/wp.sqlite --bericht-ordner reports`.
Konfiguration und ntfy-Alarmierung stehen in
[`docs/architektur.md`](docs/architektur.md#integrierter-dauerbetrieb).
Die Supervisor-App und der Multi-Architektur-Image-Build liegen unter
[`wp-analyse/`](wp-analyse/).
Modbus und eine Stromzähler-Quelle (für die Arbeitszahl) sind noch nicht implementiert.

## Echtbetrieb
```powershell
pip install -e ".[luxtronik,dashboard]"
$env:LUXTRONIK_HOST = "192.168.178.116"
python -m wpanalyse.monitor                          # Dauerabfrage alle 60 s nach data/wp.sqlite
python -m streamlit run src\wpanalyse\testseite.py   # manuelle Einzelabfrage
```

## Dashboard
```bash
pip install -e ".[dashboard]"
python -m streamlit run src/wpanalyse/dashboard.py
```
Das Dashboard hat zwei Datenquellen (Seitenleiste): **Live-Betrieb** (Abfrage alle 60 s) und
**Simulation**. Es zeigt aktuelle Werte, Temperatur-, Leistungs- und Laufzeitverläufe,
Verdichterstarts pro Tag und gesamt, die Bewertung von Anläufen zur Betriebszeit, die
Arbeitszahl über der Außentemperatur sowie eine freie Auswahl aller gespeicherten Messwerte.

Die Sidebar-Option **Anwendungslogs** und die Logstufe `DEBUG` aktivieren Ablaufdiagnosen
im Terminal des Dashboard-Prozesses. DEBUG-Zeilen enthalten die Prozess-ID (`pid`),
Logger und Funktion (`quelle`) sowie sichere Diagnosewerte wie Intervall, Anzahl und
Dauer. Adressen, Zugangsdaten, Dateipfade und Messwerte werden dafür nicht ausgegeben.
Ein bereits laufendes Dashboard muss nach Codeänderungen neu gestartet werden.

## Aufbau
| Ordner | Inhalt |
|---|---|
| `.github/copilot-instructions.md` | Regeln, die **jeder** Agent befolgt |
| `.github/agents/` | In VS Code und GitHub auswählbare Agenten: Architekt, Datensammler, Analyst, Alarm, Tester und Reviewer |
| `docs/lernpfad.md` | **Hier anfangen**: Schritt-für-Schritt lernen, mit Agenten zu arbeiten |
| `docs/architektur.md` | Datenfluss und Module |
| `docs/fachwissen.md` | Kennzahlen und Anomalie-Regeln für Wärmepumpen |
| `docs/backlog.md` | Issues mit Entwicklungsstatus und belegten Einschränkungen |
| `src/wpanalyse/` | Code-Gerüst (Datenmodell, Adapter, erste Analyse) |

## Agenten auswählen
Öffne in VS Code den Repository-Ordner als Workspace und wähle im Chat-Agenten-Auswahlmenü
einen Agenten wie **Analyst** oder **Tester**. Die Profile liegen unter `.github/agents/*.agent.md`.
Auf GitHub findest du sie im Repository im Tab **Agents**; nach Änderungen müssen die Profile
auf `main` liegen. Wähle dort den Agenten im Copilot-Auswahlmenü beim Prompt aus.
Die Dateien sind auch direkt unter
[`.github/agents/`](https://github.com/matzesonic1/wp-analyse/tree/main/.github/agents) einsehbar.
