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
| 9 | Dauerbetrieb (Scheduler: sammeln → analysieren → melden) | architekt → alle | – | 6, 7 |
| 9a | Sammeln und Speichern orchestrieren | datensammler | D | 2, 7 |
| 9b | Regelprüfung und Alarmierung orchestrieren | alarm | D | 1, 3, 4, 6, 7 |
| 9c | Tagesbericht aus dem Speicher erzeugen | analyst | D | 7, 8 |
| 9d | CLI und Scheduler integrieren | architekt | – | 9a, 9b, 9c |
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
**Ziel:** Kommando `python -m wpanalyse.run`: alle X Minuten sammeln, alle 15 min Regeln prüfen und täglich einen Bericht erzeugen. Das Issue ist in 9a–9d zerlegt; 9a–9c können parallel bearbeitet werden. Docker-Betrieb (z. B. auf Raspberry Pi / NAS) bleibt späteren Issues vorbehalten.

#### Teil-Issue 9a – Sammeln und Speichern orchestrieren
**Agent:** datensammler
**Ziel:** Adapter und Speicher für einen Sammellauf verbinden, ohne den Scheduler vorwegzunehmen.
**Betroffene Dateien:** `src/wpanalyse/erfassung.py`, `tests/test_erfassung.py`.
**Schnittstelle:** `sammle_und_speichere(adapter: DatenAdapter, speicher: SQLiteSpeicher, von: datetime, bis: datetime) -> pd.DataFrame`.
**Akzeptanzkriterien:**
- Ruft den Adapter für den halboffenen Zeitraum `[von, bis)` auf und speichert das Ergebnis unverändert im Speicher.
- Gibt die gesammelten Messwerte zurück, damit Aufrufer den Lauf nachvollziehen können.
- Adapter- und Speicherfehler werden nicht verschluckt oder als erfolgreicher Lauf ausgegeben.
- Die Funktion enthält keine eigene Zeitplanung.
**Testidee:** Mit Fake-Adapter und SQLite-Testdaten prüfen, dass Zeitraum, zurückgegebener DataFrame und gespeicherte Messwerte übereinstimmen; Fehler des Adapters werden weitergereicht.

#### Teil-Issue 9b – Regelprüfung und Alarmierung orchestrieren
**Agent:** alarm
**Ziel:** Gespeicherte Messwerte durch die bestehenden Analysen führen und den vollständigen Befundstand an den Alarmmanager übergeben.
**Betroffene Dateien:** `src/wpanalyse/monitoring.py`, `tests/test_monitoring.py`.
**Schnittstelle:** `pruefe_und_melde(speicher: SQLiteSpeicher, alarm_manager: AlarmManager, cfg: Config, von: datetime, bis: datetime) -> list[Befund]`.
**Akzeptanzkriterien:**
- Liest den angefragten Zeitraum und führt Taktungs-, Effizienz-, Spreizungs- und Komfortanalyse aus.
- Übergibt alle aktuellen Befunde gesammelt genau einmal an `AlarmManager.verarbeite`, auch wenn die Liste leer ist, damit Entwarnungen funktionieren.
- Fehlende optionale Messwertfelder erzeugen keinen unbehandelten `KeyError`; nicht auswertbare Regeln werden kenntlich gemacht und lösen keine falsche Entwarnung aus.
- Enthält keine eigene Zeitplanung und versendet selbst keine Meldungen am Alarmmanager vorbei.
**Testidee:** Fake-Speicher und Fake-Alarmmanager prüfen gelesenen Zeitraum, zusammengeführte Befunde sowie den Aufruf mit leerem Befundstand.

#### Teil-Issue 9c – Tagesbericht aus dem Speicher erzeugen
**Agent:** analyst
**Ziel:** Tagesdaten laden, mit dem bestehenden Berichtsgenerator formatieren und den Bericht als Datei ablegen.
**Betroffene Dateien:** `src/wpanalyse/tageslauf.py`, `tests/test_tageslauf.py`.
**Schnittstelle:** `erzeuge_tagesbericht(speicher: SQLiteSpeicher, cfg: Config, tag: date, ziel: Path) -> Path`.
**Akzeptanzkriterien:**
- Liest den gewählten Kalendertag als halboffenen UTC-Zeitraum `[00:00, Folgetag 00:00)` und verwendet `erstelle_tagesbericht`.
- Schreibt den Markdown-Bericht unter `ziel` und gibt den verwendeten Dateipfad zurück.
- Ein Tag ohne Messwerte erzeugt den bereits vorgesehenen verständlichen Leerbericht.
- Datei- und Speicherfehler werden nicht verschluckt.
**Testidee:** Mit SQLite und temporärem Verzeichnis einen Bericht mit sowie ohne Messwerte erzeugen und Inhalt, Datum und Rückgabepfad prüfen.

#### Teil-Issue 9d – CLI und Scheduler integrieren
**Agent:** architekt
**Ziel:** Die Teilfunktionen als startbaren Dauerbetrieb unter `python -m wpanalyse.run` verbinden.
**Betroffene Dateien:** `src/wpanalyse/run.py`, `tests/test_run.py`, `docs/architektur.md`.
**Schnittstelle:** `main(argv: Sequence[str] | None = None) -> int`; interne Abhängigkeiten für Adapter, Speicher, Alarmmanager, Uhr und Laufaktionen müssen für Tests austauschbar sein.
**Akzeptanzkriterien:**
- Bietet ein konfigurierbares Sammelintervall (X Minuten), prüft Regeln alle 15 Minuten und erzeugt täglich einen Bericht.
- Verwendet die Teilfunktionen 9a–9c; Logik für Sammeln, Analysieren und Berichtserzeugung wird nicht dupliziert.
- Unterstützt geordnetes Beenden, z. B. mit Strg+C, und lässt Fehler eines Laufs sichtbar werden, ohne den Erfolg dieses Laufs vorzutäuschen.
- Dokumentiert Start, Konfiguration und den Laufzeit-Datenfluss in `docs/architektur.md`.
- Startet über `python -m wpanalyse.run`; Tests benötigen weder echte API-Zugangsdaten noch Wartezeiten.
**Testidee:** Scheduler mit kontrollierter Uhr und Fake-Laufaktionen prüfen, dass Sammel-, Prüf- und Tagesberichtsläufe zu den vorgesehenen Intervallen ausgelöst werden; zusätzlich CLI-Start und geordnetes Beenden testen.

### Issue 10 – Dashboard
**Ziel:** Streamlit-App mit Verläufen (Vorlauf/Rücklauf/Außen, Leistung, Starts/Tag, AZ über Außentemperatur).
