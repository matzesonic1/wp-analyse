# Novelan LADV9 über Home Assistant

`NovelanLadv9Adapter` liest Zustände und Verlauf aus der Home-Assistant-REST-API.
Die Zugangsdaten kommen aus `HA_URL` und `HA_TOKEN`; die Beispiele für optionale
Entity-IDs stehen in `.env.example`. Die Namen der Entitäten hängen von der in
Home Assistant installierten Novelan-Integration ab. Über `sensoren` können sie
auch direkt beim Erzeugen des Adapters angegeben werden.

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

Die Feldnamen entsprechen den Messwerten aus `docs/fachwissen.md`. Zahlenwerte
werden als `float`, Binärsensoren als `bool` und Betriebsart/Störung als Text
geliefert. Nicht verfügbare oder ungültige numerische Zustände werden zu `NaN`
(`pd.NA`). Raumtemperaturen können über `sensoren={"raum_wohnzimmer_c":
"sensor.wohnzimmer_temperatur"}` ergänzt werden.

Beispiel:

```python
from wpanalyse.adapters.novelan_ladv9 import NovelanLadv9Adapter

adapter = NovelanLadv9Adapter()
messwerte = adapter.lese(von, bis)
```
