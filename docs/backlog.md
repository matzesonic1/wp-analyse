# Backlog – Issues zum Verteilen an Agenten

Jedes Issue ist so geschnitten, dass ein Agent es in einem PR erledigen kann.
**Parallel-Gruppe**: Issues derselben Gruppe berühren keine gemeinsamen Dateien und können gleichzeitig laufen.

| # | Titel | Agent | Parallel-Gruppe | Abhängig von |
|---|---|---|---|---|
| 1 | Spreizungs-Analyse | analyst | A | – |
| 2 | Adapter für meine Wärmepumpe | datensammler | A | – |
| 3 | Heizstab- und Effizienz-Analyse | analyst | B | 1 |
| 4 | Raumkomfort-Analyse | analyst | C | – |
| 5 | Simulation: Fehlerszenarien | tester | A | – |
| 6 | Alarm-Grundgerüst mit Telegram/ntfy | alarm | B | – |
| 7 | SQLite-Speicher | datensammler | B | 2 |
| 8 | Tagesbericht | analyst | – | 1, 3, 4 |
| 9.1 | Scheduler-Grundlage | datensammler | C | – |
| 9.2 | Geplante Messwerterfassung | datensammler | C | 2, 7 |
| 9.3 | Geplante Regelprüfung und Meldungen | alarm | C | 1, 3, 4, 6 |
| 9.4 | Dauerbetrieb-Kommando und Tagesbericht | datensammler | – | 8, 9.1, 9.2, 9.3 |
| 10 | Dashboard (Streamlit) | analyst | – | 7 |

---

### Issue 1 – Spreizungs-Analyse
**Ziel:** `src/wpanalyse/analyse/spreizung.py` mit `analysiere_spreizung(df, cfg) -> SpreizungErgebnis`.
**Akzeptanz:** mittlere Spreizung nur bei laufendem Verdichter; Regel A3 aus `fachwissen.md`; Bewertung + Klartext; Tests für Normalfall und „verschmutzter Filter“.
**Muster:** `analyse/taktung.py`.

### Issue 2 – Adapter für meine Wärmepumpe
**Ziel:** neuer Adapter in `src/wpanalyse/adapters/` für *(Marke/Modell/Schnittstelle eintragen, z. B. Home Assistant REST-API)*.
**Akzeptanz:** implementiert `DatenAdapter`; Zugangsdaten aus Umgebungsvariablen, `.env.example` ergänzt; Mapping der Herstellerfelder auf `fachwissen.md`-Felder dokumentiert; Tests mit gemockten Antworten.

### Issue 3 – Heizstab- und Effizienz-Analyse
**Ziel:** `analyse/effizienz.py` – Tages-AZ, Bewertung abhängig von Außentemperatur (A2), Heizstab-Regel (A4).
**Akzeptanz:** funktioniert auch ohne `waerme_kwh` (dann nur Heizstab-Regel und Hinweis „AZ nicht berechenbar“).

### Issue 4 – Raumkomfort-Analyse
**Ziel:** `analyse/komfort.py` – je Raum Anteil Zeit unter Soll, Regeln A5/A6, kältester Raum, Hinweis auf hydraulischen Abgleich.
**Akzeptanz:** Raum-Sollwerte aus `config.py`; beliebig viele `raum_*_c`-Spalten.

### Issue 5 – Simulation: Fehlerszenarien
**Ziel:** `simulation.py` um Szenarien erweitern: `filter_verschmutzt`, `heizstab_mild`, `raum_kalt`, `datenluecke`, `stoerung`.
**Akzeptanz:** jedes Szenario per Parameter aktivierbar; Tests prüfen, dass das Szenario in den Daten sichtbar ist.

### Issue 6 – Alarm-Grundgerüst
**Ziel:** `src/wpanalyse/alarm/` mit `Melder`-Interface, `NtfyMelder` und/oder `TelegramMelder`, Entprellung (gleiche Meldung max. 1×/6 h), Entwarnung.
**Akzeptanz:** Tests mit `FakeMelder`.

### Issue 7 – SQLite-Speicher
**Ziel:** `src/wpanalyse/speicher/` – Messwerte speichern/laden als DataFrame für Zeitraum.

### Issue 8 – Tagesbericht
**Ziel:** Text/Markdown-Bericht: AZ, Starts, Laufzeit, Spreizung, Komfort je Raum, Auffälligkeiten – verständlich für Laien.

### Issue 9 – Dauerbetrieb
Issue 9 wird in vier Teil-Issues umgesetzt. Die Teil-Issues der Parallel-Gruppe C können gleichzeitig bearbeitet werden; 9.4 integriert ihre Ergebnisse.

#### Issue 9.1 – Scheduler-Grundlage
**Ziel:** Zeitgesteuerte Aufgaben mit konfigurierbarem Sammelintervall und täglichem Ausführungszeitpunkt planen.
**Dateien:** `src/wpanalyse/config.py`, `src/wpanalyse/scheduler.py`, `tests/test_scheduler.py`.
**Schnittstelle (Skizze):** `starte_scheduler(aufgaben: list[GeplanteAufgabe], uhr: Uhr) -> None`.
**Akzeptanz:** Regelintervall beträgt 15 Minuten; Sammelintervall und tägliche Berichtszeit sind konfigurierbar; eine fehlerhafte Aufgabe beendet nicht den Scheduler; Zeitsteuerung ist mit einer injizierbaren Uhr testbar.
**Testidee:** Fake-Uhr vorspulen und Aufrufzeitpunkte, Intervallgrenzen sowie Verhalten nach einem Aufgabenfehler prüfen.
**Agent:** `datensammler`.

#### Issue 9.2 – Geplante Messwerterfassung
**Ziel:** Adapter regelmäßig auslesen und Messwerte im vorhandenen Speicher ablegen.
**Dateien:** `src/wpanalyse/sammlung.py`, `tests/test_sammlung.py`.
**Schnittstelle (Skizze):** `erfasse_messwerte(adapter: DatenAdapter, speicher: SQLiteSpeicher, von: datetime, bis: datetime) -> None`.
**Akzeptanz:** Verwendet `DatenAdapter.lese(von, bis)` und `SQLiteSpeicher.speichern(...)`; ein Adapter- oder Speicherfehler wird als Aufgabenfehler gemeldet und verhindert keinen späteren Scheduler-Lauf.
**Testidee:** Fake-Adapter und Fake-Speicher prüfen Zeitraum, neue Messwerte, leere Daten und Fehlerfälle.
**Agent:** `datensammler`.

#### Issue 9.3 – Geplante Regelprüfung und Meldungen
**Ziel:** Gespeicherte Messwerte alle 15 Minuten analysieren und neue Befunde über das bestehende Alarm-Modul melden.
**Dateien:** `src/wpanalyse/regelpruefung.py`, `tests/test_regelpruefung.py`.
**Schnittstelle (Skizze):** `pruefe_regeln(speicher: SQLiteSpeicher, alarm: AlarmManager, jetzt: datetime) -> None`.
**Akzeptanz:** Verwendet vorhandene Analysefunktionen und `AlarmManager.verarbeite(...)`; fehlende oder unzureichende Messdaten führen zu keinem Absturz; Fehler beim Melden beenden keinen späteren Scheduler-Lauf.
**Testidee:** Synthetische Messwerte mit und ohne Befund sowie Fake-Melder für neue, entprellte und fehlerhafte Meldungen verwenden.
**Agent:** `alarm`.

#### Issue 9.4 – Dauerbetrieb-Kommando und Tagesbericht
**Ziel:** `python -m wpanalyse.run` startet Scheduler, Erfassung, Regelprüfung und täglichen Bericht als zusammenhängenden Prozess.
**Dateien:** `src/wpanalyse/run.py`, `docs/architektur.md`, `tests/test_run.py`.
**Schnittstelle (Skizze):** `main() -> None`; intern werden `erfasse_messwerte(...)`, `pruefe_regeln(...)` und `erstelle_tagesbericht(...)` als geplante Aufgaben verbunden.
**Akzeptanz:** Das Kommando sammelt im konfigurierten Intervall, prüft Regeln alle 15 Minuten und erstellt täglich genau einen Bericht; beendet sich kontrolliert bei `Ctrl+C`; der Ablauf und Datenfluss sind in der Architektur dokumentiert. Docker-Betrieb bleibt ein Folge-Issue.
**Testidee:** Integrationstest mit Fake-Uhr, Fake-Adapter, Fake-Speicher und Fake-Melder prüft Zeitplan, Tagesbericht und kontrolliertes Beenden.
**Agent:** `datensammler`.

### Issue 10 – Dashboard
**Ziel:** Streamlit-App mit Verläufen (Vorlauf/Rücklauf/Außen, Leistung, Starts/Tag, AZ über Außentemperatur).
