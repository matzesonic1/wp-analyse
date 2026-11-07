# WP-Analyse auf einem Raspberry Pi mit Home Assistant

## Kurzantwort

WP-Analyse kann als eigenständige Python-Anwendung laufen. Auf einem Raspberry Pi,
auf dem das offizielle **Home Assistant OS** installiert ist, sollte sie aber nicht
wie auf einem normalen Linux-System direkt mit `pip` und einem eigenen systemd-Dienst
installiert werden: Home Assistant OS ist ein verwaltetes Appliance-System. Der
vorgesehene Weg für zusätzliche Anwendungen ist eine **Home-Assistant-App** (früher
Add-on), die als eigener Container vom Supervisor verwaltet wird.

Für dieses Projekt ist eine solche App der empfohlene Zielweg, wenn WP-Analyse auf
demselben Raspberry Pi wie Home Assistant laufen soll. Sie bleibt ein eigener
Prozess und nutzt Home Assistant als Datenquelle über dessen REST-API. Eine native
Home-Assistant-Integration wäre ein anderes, deutlich umfangreicheres Produkt:
Derzeit gibt es in diesem Repository keine Integration, die WP-Analyse als
Home-Assistant-Entitäten oder -Konfiguration bereitstellt.

## Bereitstellungsoptionen

| Weg | Geeignet für | Bewertung |
|---|---|---|
| Home-Assistant-App auf Home Assistant OS | WP-Analyse auf demselben Pi, Start/Stop und Updates über Home Assistant | **Empfohlen.** App-Container, Konfiguration und persistenter Speicher müssen noch ergänzt werden. |
| Eigenständiger Prozess auf einem separaten Linux-Rechner oder Pi | Unabhängiger Betrieb und normale Linux-Werkzeuge | Schon heute für CLI und Streamlit möglich. Der Rechner muss Home Assistant im LAN erreichen. |
| Eigener Container neben Home Assistant Container | Docker-/Container-Installationen ohne Supervisor | Möglich, aber Installation, Neustart und Updates werden außerhalb von Home Assistant verwaltet. |
| Native Home-Assistant-Integration | WP-Analyse-Einstellungen und Ergebnisse als native HA-Entitäten/-Flows | Nicht der erste Schritt. Dafür müsste das Projekt in eine Integration umgebaut und enger an Home Assistant gekoppelt werden. |

Home Assistant OS auf dem Raspberry Pi enthält Core und Supervisor und unterstützt
Apps. Der Container-Installationsweg ist dagegen eine eigenständige Core-Installation;
er stellt nicht dieselbe Supervisor-App-Verwaltung bereit. Deshalb ist eine
Home-Assistant-App keine direkt installierbare Python-Anwendung auf dem HA-OS-Host.

## Stand dieses Repositories

- `NovelanLadv9Adapter` liest Zustände und Verlauf über die Home-Assistant-REST-API.
  URL, Zugriffstoken und Entity-IDs werden über Umgebungsvariablen konfiguriert.
- Der Adapter ist noch nicht mit einem dauerhaft laufenden Sammel- und Speicherprozess
  verbunden. `docs/novelan-ladv9-adapter.md` beschreibt den manuellen Abruf.
- `Monitor` kann bereits einen Adapter periodisch abfragen und SQLite verwenden; der
  ausführbare Einstiegspunkt `python -m wpanalyse.monitor` konfiguriert aber
  ausschließlich den Luxtronik-Adapter.
- Das Streamlit-Dashboard ist eine separate Anwendung. Derzeit ist es nicht als
  Home-Assistant-App oder über eine Home-Assistant-Seitenleiste eingebunden.

Damit ist der Home-Assistant-Datenadapter vorhanden, eine schlüsselfertige
HA-OS-Installation aber noch nicht.

## Empfohlener Datenfluss

```text
Wärmepumpe → Home-Assistant-Integration → HA-Entitäten / HA-Verlauf
                                           │ REST-API (lesend)
                                           ▼
                              WP-Analyse-App (eigener Container)
                              NovelanLadv9Adapter → Monitor → SQLite
                                           │
                                           └── später optional: Dashboard / HA-Ausgabe
```

Die App sollte nur die konfigurierten Entitäten lesen. Die lokale SQLite-Datei muss
in einem vom Supervisor dauerhaft bereitgestellten App-Datenverzeichnis liegen, nicht
im schreibbaren Container-Dateisystem. Ein Container-Neustart oder App-Update darf
die Messhistorie nicht löschen. Für den ersten Schritt ist kein eingehender Netzwerkport
erforderlich; die App fragt Home Assistant ab.

## Umsetzung in kleinen Schritten

Die Issues bauen aufeinander auf und sollten nacheinander umgesetzt werden. Ein
nativer HA-Sensor-Export ist optional und kann unabhängig von der App-Verpackung
später entschieden werden.

### Issue A – Home-Assistant-Monitor dauerhaft starten

- **Ziel:** Den bestehenden Home-Assistant-Adapter mit periodischer Abfrage und
  SQLite-Speicherung als CLI nutzbar machen.
- **Agent:** `datensammler`
- **Betroffene Dateien:** `src/wpanalyse/ha_monitor.py`,
  `tests/test_ha_monitor.py`, gegebenenfalls `docs/novelan-ladv9-adapter.md`.
- **Schnittstelle:** `main(argv: Sequence[str] | None = None) -> int`
- **Akzeptanzkriterien:**
  - Konfiguriert `NovelanLadv9Adapter` aus der vorhandenen Umgebungskonfiguration
    und startet den vorhandenen generischen `Monitor`.
  - Unterstützt Intervall und Datenbankpfad; die Datenbank wird unter dem
    konfigurierten Pfad angelegt.
  - Beendet den Prozess geordnet und protokolliert API-/Speicherfehler, ohne
    Zugangstoken oder vollständige Authentifizierungsheader auszugeben.
  - Überschreibt keine der bestehenden Luxtronik-CLI-Funktionen.
- **Testidee:** Mit gemockter API beziehungsweise Fake-Adapter und temporärer SQLite-
  Datenbank prüfen, dass Messwerte gespeichert, Fehler sichtbar und Stop/Intervall
  ohne reale Wartezeit testbar sind.
- **Abhängigkeit:** keine; muss vor Issue B abgeschlossen sein.

### Issue B – Home-Assistant-App für Home Assistant OS verpacken

- **Ziel:** Den Einstiegspunkt aus Issue A als vom Supervisor installierbare App
  bereitstellen.
- **Agent:** `datensammler`
- **Betroffene Dateien:** neue App-Verzeichnisstruktur (App-Metadaten,
  Container-Builddatei, Startkonfiguration), Build-/Dokumentationsdateien.
- **Schnittstelle:** Container-Startbefehl `python -m wpanalyse.ha_monitor`;
  App-Optionen für HA-API-URL, Token, Entity-IDs und Intervall werden auf die
  bestehende Prozesskonfiguration abgebildet.
- **Akzeptanzkriterien:**
  - Installierbar aus einem benutzerdefinierten App-Repository auf Home Assistant OS.
  - Unterstützte Raspberry-Pi-Architekturen werden explizit festgelegt und die
    Images für diese Architekturen gebaut. Vor Veröffentlichung ist die Zielhardware
    anzugeben und praktisch zu testen.
  - SQLite liegt im persistenten App-Datenverzeichnis; Logs gehen an die
    Container-Ausgabe und der Supervisor kann den Prozess verwalten.
  - Kein unnötiger eingehender Netzwerkzugriff. Token und sonstige Geheimnisse
    werden nicht in Git, Image-Layern oder Logs abgelegt.
- **Testidee:** Image bauen und mit einer simulierten Home-Assistant-API starten;
  Installieren, Neustarten und Update auf dem konkret unterstützten Home-Assistant-
  OS/Raspberry-Pi-Modell prüfen und Datenpersistenz verifizieren.
- **Abhängigkeit:** Issue A.

### Optional – Analyseergebnisse in Home Assistant anzeigen

Die App-Installation allein erzeugt noch keine WP-Analyse-Entitäten in Home
Assistant. Falls Messwerte oder Analysebefunde in HA-Dashboards und Automationen
verwendet werden sollen, dafür ein eigenes Folge-Issue schneiden. Vor der Umsetzung
ist zwischen einer passenden Veröffentlichungsschnittstelle (zum Beispiel MQTT)
und einer nativen Custom Integration zu entscheiden. Dabei müssen Entity-Namen,
Einheiten, Verfügbarkeit und das Verhalten bei veralteten Messwerten festgelegt
werden. Ein nativer Umbau ist nicht Voraussetzung für die empfohlene App.

## Installation bis zur fertigen App

### Eigenständiger Betrieb auf einem separaten Rechner

Der bestehende Projekt-Schnellstart und die Dokumentation
[`novelan-ladv9-adapter.md`](novelan-ladv9-adapter.md) gelten weiterhin. Den Prozess
auf einem unterstützten Linux-System oder in einem selbst verwalteten Container
starten; `HA_URL`, `HA_TOKEN` und die benötigten `NOVELAN_ENTITY_*`-Variablen müssen
in dessen Umgebung gesetzt sein. Home Assistant und der Prozess müssen sich im
lokalen Netz erreichen. Keine Wärmepumpen- oder Home-Assistant-Ports ins Internet
freigeben.

### Betrieb auf demselben Raspberry Pi mit Home Assistant OS

Bis Issue B verfügbar ist, gibt es keinen unterstützten direkten Installationsweg
auf den HA-OS-Host. Nach Umsetzung der Issues wäre der Ablauf:

1. In Home Assistant das benutzerdefinierte WP-Analyse-App-Repository hinzufügen
   und die App installieren.
2. HA-API-Verbindung, benötigte Entity-IDs und Sammelintervall in der App
   konfigurieren. Ein Zugriffstoken nur nach dem für die App dokumentierten,
   sicheren Konfigurationsweg bereitstellen; nicht in ein öffentliches Issue,
   Repository oder Log kopieren.
3. App starten und in den App-Logs API-Erreichbarkeit und erste erfolgreiche
   Messwertspeicherung prüfen.
4. Nach Neustart und App-Update prüfen, dass die SQLite-Historie erhalten bleibt.
5. Für die spätere Anzeige das separate Streamlit-Dashboard beziehungsweise eine
   Ausgabe an Home Assistant als eigenen Funktionsumfang ergänzen.

Vor der Freigabe müssen Raspberry-Pi-Modell, HA-OS-Architektur, App-Image,
Speicherverhalten und Upgrade-/Backup-Verhalten praktisch getestet sein.

## Quellen

- [Home Assistant auf einem Raspberry Pi installieren](https://www.home-assistant.io/installation/raspberrypi/) – Home Assistant OS, Supervisor und Apps.
- [Home Assistant-Installationsarten](https://www.home-assistant.io/installation/) – Einordnung von Home Assistant OS und Container-Installation.
- [Home Assistant Apps veröffentlichen](https://developers.home-assistant.io/docs/apps/publishing/) – Container-Images, Architekturen und Veröffentlichung; vor einem App-Release die aktuelle Anleitung und Beispiel-App beachten.
- [Home Assistant API](https://www.home-assistant.io/integrations/api/) – REST-API der Home-Assistant-Instanz.
- [Home-Assistant-Adapter im Projekt](novelan-ladv9-adapter.md) – Einrichtung, Token, Entity-Mapping und Grenzen des bestehenden Adapters.
