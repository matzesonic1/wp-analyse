# Novelan LADV9 über Home Assistant

## Verbindungsweg

Der vorhandene Adapter verbindet sich **nicht direkt** mit der Wärmepumpe. Der
Datenfluss ist:

```text
Novelan LADV9.1-1/3 → Netzwerkzugriff des Reglers → Home-Assistant-Integration
                    → Home-Assistant-Entitäten → NovelanLadv9Adapter → DataFrame
```

Ein möglicher Weg ist eine Home-Assistant-Integration für Luxtronik 2.0, zum
Beispiel [notDIRK/luxtronik2-hass](https://github.com/notDIRK/luxtronik2-hass).
Diese Community-Integration ist keine offizielle Novelan-Software. Vor dem
Einrichten muss am konkreten Gerät geprüft werden, welcher Regler und
Firmwarestand verbaut sind und ob die Integration damit funktioniert. Die
Modellbezeichnung LADV9.1-1/3 allein garantiert diese Kompatibilität nicht.
Bei Unsicherheit Reglerdaten beim Installateur erfragen.

### Einrichtung und erster Datenabruf

1. Regler und Home Assistant müssen im lokalen Netzwerk erreichbar sein. Eine
   feste DHCP-Zuordnung für den Regler erleichtert die Einrichtung. Keine Ports
   des Reglers ins Internet freigeben.
2. Installiere die gewählte Luxtronik-Integration nach deren aktueller Anleitung
   und füge den Regler in Home Assistant hinzu. Prüfe danach in Home Assistant
   unter **Entwicklerwerkzeuge → Zustände**, welche Sensoren tatsächlich
   vorhanden sind. Die Entitäts-IDs können je nach Integration und Konfiguration
   abweichen. Diese Integration kann auch Steuer-Entitäten bereitstellen; dieser
   Adapter verwendet sie nicht.
3. Erstelle in Home Assistant ein langlebiges Zugriffstoken für den
   Anwendungszugriff. Halte URL und Token für den Prozess bereit, in dem
   WP-Analyse läuft. Das Token ist ein Geheimnis und gehört weder in den
   Quellcode noch in Git. `.env.example` enthält nur Beispielnamen; Python lädt
   eine `.env`-Datei nicht automatisch. Die Variablen müssen durch die Shell,
   einen Dienstmanager oder eine andere sichere Konfiguration in die
   Prozessumgebung exportiert werden.
4. Ordne die in Home Assistant gefundenen IDs den Projektfeldern über die
   `NOVELAN_ENTITY_*`-Variablen zu (siehe `.env.example`). Für Analysen müssen
   mindestens die benötigten Messwerte konfiguriert sein; nicht benötigte
   Entitäten können leer bleiben.

   Beispiel für Bash mit einer Entität; die übrigen IDs setzt du entsprechend
   deiner Home-Assistant-Entitäten:

   ```bash
   export HA_URL='http://homeassistant.local:8123'
   export NOVELAN_ENTITY_AUSSEN_C='sensor.novelan_aussentemperatur'
   read -rsp 'Home-Assistant-Token: ' HA_TOKEN && printf '\n' && export HA_TOKEN
   ```

5. Prüfe Einheiten, Werte und Verlauf der ausgewählten Entitäten in Home
   Assistant, bevor du die Daten auswertest. Der Adapter wandelt numerische
   Zustände in `float` um, rechnet aber **keine Einheiten um** und leitet keine
   fehlenden Werte ab. Insbesondere bei Strom- und Wärmemengenzählern müssen
   Einheit und Bedeutung des Zählerstands zum Feld passen. Der historische
   Abruf funktioniert nur für Daten, die Home Assistant noch im Verlauf
   gespeichert hat.
6. Rufe den Adapter zunächst manuell für einen kurzen Zeitraum auf und vergleiche
   die Werte mit Home Assistant beziehungsweise der Regleranzeige:

   ```python
   from datetime import UTC, datetime, timedelta

   from wpanalyse.adapters.novelan_ladv9 import NovelanLadv9Adapter

   bis = datetime.now(UTC)
   adapter = NovelanLadv9Adapter()
   messwerte = adapter.lese(bis - timedelta(hours=24), bis)
   print(messwerte.tail())
   ```

`lese(von, bis)` fragt den Home-Assistant-Verlauf im Zeitraum `[von, bis)` ab;
`aktuell()` liest die aktuellen Zustände. Beide Methoden verwenden die
Home-Assistant-REST-API. Ein dauerhaft laufender Erfassungsprozess, der den
Adapter regelmäßig aufruft und Messwerte speichert, ist derzeit noch nicht
implementiert.

## Entitäts-Mapping

| Home-Assistant-Entität | DataFrame-Feld |
|---|---|
| Außentemperatur-Sensor | `aussen_c` |
| Vorlauf-Sensor | `vorlauf_c` |
| Rücklauf-Sensor | `ruecklauf_c` |
| Verdichter-Binärsensor | `verdichter_an` |
| Verdichterfrequenz-Sensor | `verdichter_hz` |
| Elektrische Leistung | `leistung_w` |
| Stromzähler | `strom_kwh` |
| Wärmemengenzähler | `waerme_kwh` |
| Heizstab-Binärsensor | `heizstab_an` |
| Betriebsart-Sensor | `betriebsart` |
| Warmwasser-Temperatur-Sensor | `warmwasser_c` |
| Störungssensor | `stoerung` |
| Raumtemperatur-Sensor (optional) | `raum_<name>_c` |

Die konkreten Entity-IDs hängen von der verwendeten Integration ab. Die
Feldnamen entsprechen den Messwerten aus `docs/fachwissen.md`. Zahlenwerte
werden als `float`, konfigurierte Binärsensoren als `bool` und Betriebsart oder
Störung als Text geliefert. Nicht verfügbare oder ungültige numerische Zustände
werden zu `NaN` (`pd.NA`). Raumtemperaturen können über
`sensoren={"raum_wohnzimmer_c": "sensor.wohnzimmer_temperatur"}` ergänzt
werden. Der Adapter benötigt eine Home-Assistant-URL, ein Token und mindestens
eine konfigurierte Entität.

Direkte Zugriffe per Hersteller-API oder Modbus sowie ein automatischer
Dauerbetrieb sind derzeit nicht Teil dieses Adapters.

## Quelle

- [Luxtronik 2.0 Home-Assistant-Integration (Community-Projekt)](https://github.com/notDIRK/luxtronik2-hass)
