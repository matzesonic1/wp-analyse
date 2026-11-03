# Direkte Anbindung an den Luxtronik-Regler (Novelan / Alpha Innotec)

Die Wärmepumpe (Novelan LADV 9.1/3 mit Alpha-Innotec-Innengerät) wird **lokal und nur lesend**
über das Luxtronik-LAN-Protokoll (TCP-Port 8889) abgefragt. Es gibt keine Cloud und keinen
Account. Modbus ist an der Anlage nicht verfügbar, myUplink ist für Luxtronik-Regler
nicht vorgesehen.

## Voraussetzungen
- Der Regler hängt per LAN im Netz und ist erreichbar (Prüfung:
  `Test-NetConnection <ip> -Port 8889`).
- Die Adresse steht in der Umgebungsvariable `LUXTRONIK_HOST`, nicht im Code.
- Installation: `pip install -e ".[luxtronik,dashboard]"`

## Starten
```powershell
$env:LUXTRONIK_HOST = "192.168.178.116"
python -m wpanalyse.monitor --einmal                    # eine Abfrage (Test im Terminal)
python -m wpanalyse.monitor                             # Dauerbetrieb, alle 60 s
python -m streamlit run src\wpanalyse\testseite.py      # Testoberfläche mit Knopf
python -m streamlit run src\wpanalyse\dashboard.py      # Dashboard (Live-Betrieb / Simulation)
```
Gespeichert wird standardmäßig in `data/wp.sqlite` (per `.gitignore` ausgeschlossen).

## Bausteine
| Datei | Aufgabe |
|---|---|
| `adapters/luxtronik.py` | `LuxtronikAdapter`: liest den Regler, liefert eine Zeile im Projektformat |
| `monitor.py` | `Monitor`: Abfrage im festen Intervall (mindestens 60 s), speichert in SQLite, fängt Fehler ab |
| `testseite.py` | Streamlit-Testoberfläche: einzelne Abfrage, 60-s-Sperre, Feldübersicht |
| `dashboard.py` | Live-Betrieb: fragt alle 60 s ab, zeigt Kacheln, Diagramme und freie Wertauswahl |
| `analyse/verdichter.py` | Anläufe im Verhältnis zur Betriebszeit (reine Funktion) |
| `config.py` | `LUXTRONIK_FELDER`, `LuxtronikConfig`, `VerdichterConfig` |

## Was abgefragt wird
Zuordnung Projektfeld → Luxtronik-ID (`LUXTRONIK_FELDER` in `config.py`):

| Gruppe | Projektfelder |
|---|---|
| Temperaturen | `aussen_c`, `vorlauf_c`, `ruecklauf_c`, `ruecklauf_soll_c`, `warmwasser_c`, `heissgas_c`, `quelle_ein_c`, `quelle_aus_c` |
| Leistung | `waerme_w` (thermische Heizleistung) |
| Verdichter | `verdichter_laufzeit_s`, `verdichter_betriebszeit_s`, `verdichter_starts_zaehler` |
| Zusatzheizung | `heizstab1_laufzeit_s`, `heizstab2_laufzeit_s` |
| Abtauung | `abtauung_zeit_s` |
| Betriebsart | `betriebsart` (aus `ID_WEB_WP_BZ_akt`, Zuordnung in `LuxtronikConfig.betriebsart_zuordnung`) |
| Abgeleitet | `verdichter_an`, `heizstab_an` |

Zusätzlich speichert der Adapter alle übrigen benannten Zahlen- und Wahrheitswerte als
Spalten `lux_<name>` (zum Beispiel `lux_ID_WEB_Freq_VD`). Unbenannte Felder (`Unknown_*`)
und Texte werden ausgelassen. Abschalten: `alle_calculations_speichern=False`.

**Nicht verfügbar:** Der Regler liefert keine elektrische Leistung. Für die Arbeitszahl
ist ein separater Stromzähler nötig (noch nicht angebunden).

## Schonung des Reglers
- Es wird nie geschrieben, nur gelesen (`safe=True`).
- Das Intervall liegt bei mindestens 60 s, auch wenn weniger angegeben wird.
- Das Dashboard fragt nur ab, wenn die letzte Messung älter als das Intervall ist; mehrere
  offene Tabs und ein parallel laufender Monitor erzeugen keine doppelten Abfragen.
- Der Regler hält keine Historie vor. Daten entstehen nur, solange der Monitor oder das
  Dashboard läuft.

## Verdichter-Bewertung
`analyse/verdichter.py` vergleicht Starts und Betriebszeit und meldet:
- mittlere Laufzeit je Start unter 10 min (Warnung) bzw. unter 30 min (Hinweis),
- mehr als 6 Starts innerhalb einer Stunde (Hinweis ab 4),
- ob die Betriebszeit seit dem Verdichtertausch (Dezember 2025) überhaupt möglich ist.

**Wichtig:** Die Zähler des Reglers wurden beim Tausch nicht zurückgesetzt (9.928 Starts und
8.671 h bei höchstens etwa 8.100 h seit dem Tausch). Mittelwerte über die Gesamtlaufzeit
sagen deshalb nichts über den neuen Verdichter. Trage in `VerdichterConfig` die Zählerstände
vom Tauschtag als `basis_starts` und `basis_betriebszeit_s` ein, oder den Stand eines
beliebigen Stichtags, ab dem gerechnet werden soll.

Die Grenzwerte sind **Richtwerte, keine geprüften Herstellerangaben**. Bitte mit dem
Datenblatt des Verdichters abgleichen und in `VerdichterConfig` anpassen.

## Bekannte Grenzen
- Die Betriebsart wird nur für bekannte Texte übersetzt, unbekannte werden roh übernommen. Die
  Zuordnung (insbesondere Abtauung) sollte nach einigen Tagen Echtdaten geprüft werden.
- `quelle_aus_c` liefert -50 °C, der Sensor ist vermutlich nicht verbaut.
- Bei Lücken im Monitoring (Prozess aus) wird der Zähler-Zuwachs dem Tag der nächsten
  Messung zugerechnet.
