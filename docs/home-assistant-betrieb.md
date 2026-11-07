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
| Home-Assistant-App auf Home Assistant OS | WP-Analyse auf demselben Pi, Start/Stop und Updates über Home Assistant | **Empfohlen.** Ein Supervisor-App-Verzeichnis und ein Multi-Architektur-Build-Workflow sind im Repository vorhanden. |
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
- `python -m wpanalyse.ha_monitor` verbindet den Adapter mit dem bestehenden
  `Monitor` und `SQLiteSpeicher`. Das Intervall und der Datenbankpfad sind über
  `--intervall`/`--db` oder `WPANALYSE_INTERVAL`/`WPANALYSE_DB` konfigurierbar.
- Unter `wp-analyse/` liegt die Supervisor-App mit persistentem Speicher unter
  `/data/wp.sqlite`; Logs gehen an die Container-Ausgabe. `repository.yaml` macht
  dieses Git-Repository als benutzerdefiniertes App-Repository erkennbar.
- `.github/workflows/build-app.yaml` ist so konfiguriert, dass bei Pushes nach
  `main` und per manuellem Start OCI-Images für `aarch64` und `amd64` gebaut und
  als Multi-Architektur-Image in GHCR veröffentlicht werden.
- Das Streamlit-Dashboard ist eine separate Anwendung. Derzeit ist es nicht als
  Home-Assistant-App oder über eine Home-Assistant-Seitenleiste eingebunden.

Die Raspberry-Pi-Unterstützung ist auf 64-Bit-Home-Assistant-OS (`aarch64`)
ausgelegt. Zusammen mit `amd64` sind dies die in der App-Metadatei und im
Build-Workflow eingetragenen Architekturen. `armv7`/32-Bit wird ausdrücklich
nicht angeboten: Es ist veraltet, und die nötige pandas-/NumPy-Wheel- oder
Quellbuild-Kompatibilität wurde dafür nicht validiert. Der lokale
amd64-Container-Build war erfolgreich; ein aarch64-Build war mangels
QEMU-Emulation in der Sandbox nicht möglich. Weder ein echtes Raspberry-Pi-Gerät
noch ein Home-Assistant-OS-Supervisor wurden getestet. Vor der allgemeinen
Freigabe müssen Image-Veröffentlichung, Installation, Neustart, Update und
Datenpersistenz auf Zielhardware geprüft werden.

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

## Umfangsgrenze

Die App-Installation allein erzeugt noch keine WP-Analyse-Entitäten in Home
Assistant. Falls Messwerte oder Analysebefunde in HA-Dashboards und Automationen
verwendet werden sollen, dafür ein eigenes Folge-Issue schneiden. Vor der Umsetzung
ist zwischen einer passenden Veröffentlichungsschnittstelle (zum Beispiel MQTT)
und einer nativen Custom Integration zu entscheiden. Dabei müssen Entity-Namen,
Einheiten, Verfügbarkeit und das Verhalten bei veralteten Messwerten festgelegt
werden. Ein nativer Umbau ist nicht Voraussetzung für die empfohlene App.

## Installation und Konfiguration

### Eigenständiger Betrieb auf einem separaten Rechner

Der bestehende Projekt-Schnellstart und die Dokumentation
[`novelan-ladv9-adapter.md`](novelan-ladv9-adapter.md) gelten weiterhin. Den Prozess
auf einem unterstützten Linux-System oder in einem selbst verwalteten Container
starten. Beispiel:

```bash
export HA_URL='http://homeassistant.local:8123'
read -rsp 'Home-Assistant-Token: ' HA_TOKEN && printf '\n' && export HA_TOKEN
export NOVELAN_ENTITY_AUSSEN_C='sensor.novelan_aussentemperatur'
python -m wpanalyse.ha_monitor --intervall 60 --db data/wp.sqlite
```

Die verfügbaren Entity-Variablen stehen in `.env.example`. `--einmal` führt nur
eine Abfrage aus. Das Pollingintervall wird zum Schutz des Reglers mindestens auf
60 Sekunden begrenzt. Netzwerkfehler lösen begrenzte Wiederholungen mit
exponentiellem Backoff aus; fehlgeschlagene Messungen werden nicht ergänzt.

### Betrieb auf demselben Raspberry Pi mit Home Assistant OS

Die App ist als benutzerdefiniertes Supervisor-App-Repository vorbereitet. Für
eine Installation mit veröffentlichtem Container-Image:

1. Das GitHub-Paket `ghcr.io/matzesonic1/wp-analyse` muss nach dem ersten
   erfolgreichen Workflow-Lauf öffentlich lesbar sein. Der Workflow erstellt
   Images für `aarch64` (64-Bit-Raspberry-Pi-HA-OS) und `amd64`. `armv7` ist
   weder in der App-Konfiguration noch im Build freigegeben.
2. In **Einstellungen → Apps → App-Repository** die Repository-URL
   `https://github.com/matzesonic1/wp-analyse` hinzufügen und die App installieren.
3. In der App-Konfiguration Home-Assistant-URL, langlebiges Token, die
   verwendeten Entity-IDs und das Intervall setzen. Das Token bleibt in der
   Supervisor-Konfiguration und wird zur Laufzeit als `HA_TOKEN` an den Prozess
   übergeben; es wird nicht in das Image kopiert oder protokolliert.
4. App starten und in den Supervisor-Logs die erfolgreiche Speicherung prüfen.
   Die SQLite-Datei liegt im persistenten App-Verzeichnis `/data/wp.sqlite`.
5. Nach Neustart und Update prüfen, dass die SQLite-Historie erhalten bleibt.

### Versionierung der App-Images

Die `version` in `wp-analyse/config.yaml` ist die maßgebliche Version der
Home-Assistant-App und des zugehörigen versionierten OCI-Images. Sie folgt
`MAJOR.MINOR.PATCH`: Erhöhe MAJOR bei inkompatiblen Änderungen, MINOR bei
rückwärtskompatiblen Funktionen und PATCH bei rückwärtskompatiblen Fehlerkorrekturen.
Jede veröffentlichte Version ist eindeutig und wird nicht wiederverwendet.

Der Build-Workflow liest diese Versionsnummer und veröffentlicht bei passenden
Pushes nach `main` sowohl das versionierte Image als auch `latest`. Da der Build
eine bereits vorhandene Versionsnummer überspringt, muss die App-Version vor
jedem Push erhöht werden, der ein neues App-Image veröffentlichen soll. Ohne
Versionswechsel kann `latest` neu gebaut werden, während das versionierte Image
beim bisherigen Stand bleibt. `latest` ist daher nur ein veränderlicher Verweis,
kein Ersatz für eine neue App-Version. Ein Release-Commit sollte zusätzlich mit
dem dazu passenden Git-Tag `vMAJOR.MINOR.PATCH` markiert werden; der Workflow
wird durch den Push nach `main`, nicht durch den Tag ausgelöst.

Die Version in `pyproject.toml` bezeichnet die Python-Distribution und wird vom
App-Image-Workflow nicht als Quelle verwendet. Sie wird unabhängig gepflegt,
solange keine Python-Paketveröffentlichung mit eigener Versionsfreigabe erfolgt.

Nach dem ersten Paket-Push ist gegebenenfalls die GHCR-Paket-Sichtbarkeit auf
**public** zu setzen. Es gibt keine eingehenden Ports.

Zielhardware-Validierung bleibt offen: Installation über den Supervisor,
Raspberry-Pi-Modell/HA-OS-Version, aarch64-Image, Container-Start, Neustart,
Update und Persistenz/Backup müssen noch praktisch geprüft werden. Der
Multi-Architektur-Build-Workflow ist eingerichtet, wurde in dieser Sandbox aber
nicht ausgeführt; das lokale amd64-Image lässt sich bauen.

## Quellen

- [Home Assistant auf einem Raspberry Pi installieren](https://www.home-assistant.io/installation/raspberrypi/) – Home Assistant OS, Supervisor und Apps.
- [Home Assistant-Installationsarten](https://www.home-assistant.io/installation/) – Einordnung von Home Assistant OS und Container-Installation.
- [Home Assistant Apps veröffentlichen](https://developers.home-assistant.io/docs/apps/publishing/) – Container-Images, Architekturen und Veröffentlichung; vor einem App-Release die aktuelle Anleitung und Beispiel-App beachten.
- [Home Assistant API](https://www.home-assistant.io/integrations/api/) – REST-API der Home-Assistant-Instanz.
- [Home-Assistant-Adapter im Projekt](novelan-ladv9-adapter.md) – Einrichtung, Token, Entity-Mapping und Grenzen des bestehenden Adapters.
