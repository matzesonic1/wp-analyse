# Fachwissen Wärmepumpe

Richtwerte für Luft-Wasser-Wärmepumpen im Einfamilienhaus. Dein Haus kann abweichen – die
Schwellwerte stehen deshalb in `config.py` und werden nach einigen Wochen Messung angepasst.

## Benötigte Messwerte
| Messwert | Feld | Pflicht |
|---|---|---|
| Außentemperatur | `aussen_c` | ja |
| Vorlauftemperatur | `vorlauf_c` | ja |
| Rücklauftemperatur | `ruecklauf_c` | ja |
| Verdichter an/aus oder Frequenz | `verdichter_an` / `verdichter_hz` | ja |
| Elektrische Leistung / Energie | `leistung_w` / `strom_kwh` | ja |
| Erzeugte Wärme | `waerme_kwh` | wenn verfügbar |
| Heizstab aktiv | `heizstab_an` | wenn verfügbar |
| Betriebsart (Heizen/WW/Abtauen/Aus) | `betriebsart` | wenn verfügbar |
| Warmwasser-Temperatur | `warmwasser_c` | optional |
| Raumtemperaturen je Raum | `raum_<name>_c` | für Komfort-Ziel |
| Fehlercodes | `stoerung` | wenn verfügbar |

## Kennzahlen

### 1. Effizienz – Arbeitszahl (AZ / COP)
`AZ = erzeugte Wärme / verbrauchter Strom` (pro Tag, Monat, Jahr = JAZ).
- Gut: JAZ ≥ 3,5 (Fußbodenheizung), ≥ 3,0 (Heizkörper). Unter 2,5 = prüfen.
- Tages-AZ immer **in Abhängigkeit der Außentemperatur** bewerten (bei −10 °C ist 2,3 normal, bei +10 °C nicht).

### 2. Schonender Betrieb – Taktung
- Verdichterstarts pro Tag: Ziel < 6–10, über 20 = deutliches Takten.
- Mittlere Laufzeit pro Zyklus: Ziel > 30 min, unter 10 min = schädlich (Verschleiß, schlechte Effizienz).
- Häufigste Ursachen: Heizkurve zu hoch, WP überdimensioniert, zu wenig Wasservolumen, Einzelraumregler schließen.

### 3. Spreizung (Vorlauf − Rücklauf)
- Fußbodenheizung: 3–7 K, Heizkörper: 5–10 K.
- Steigt die Spreizung langsam über Wochen → Durchfluss sinkt (Filter/Schmutzfänger verschmutzt, Luft im System).
- Sehr kleine Spreizung (< 2 K) bei Betrieb → Pumpe zu stark oder Wärme wird nicht abgenommen.

### 4. Heizkurve / Vorlauftemperatur
- Je niedriger der Vorlauf, desto effizienter (~2,5 % Effizienz pro K).
- Sind alle Räume deutlich über Soll → Heizkurve kann gesenkt werden.

### 5. Heizstab
- Sollte praktisch nur bei sehr tiefen Temperaturen oder Legionellenschaltung laufen.
- Heizstab aktiv bei Außentemperatur > −5 °C → Warnung.

### 6. Abtauung
- Bei 0 bis +7 °C und hoher Luftfeuchte häufig, das ist normal.
- Sehr viele Abtauungen (> 2–3 pro Stunde) oder Abtauung bei trockener Kälte → Verdampfer/Luftführung prüfen.

### 7. Komfort – „überall warm genug“
- Je Raum: Anteil der Zeit unter Soll − 1 K (z. B. Wohnraum 20 °C, Bad 22 °C, Schlafzimmer 18 °C).
- Ein Raum dauerhaft kälter als die anderen → hydraulischer Abgleich prüfen.
- Raum kalt **und** WP läuft am Limit → WP zu klein oder Heizkurve zu niedrig.

## Anomalie-Regeln (Startversion)
| ID | Regel | Schwere |
|---|---|---|
| A1 | > 20 Verdichterstarts/Tag oder Zykluslaufzeit < 10 min | warnung |
| A2 | Tages-AZ > 20 % unter Erwartung für diese Außentemperatur | warnung |
| A3 | Spreizung 7-Tage-Mittel > 30 % über 30-Tage-Mittel | hinweis |
| A4 | Heizstab aktiv bei Außentemperatur > −5 °C | warnung |
| A5 | Raumtemperatur > 2 h unter Soll − 1,5 K | warnung |
| A6 | Raumtemperatur < 17 °C | kritisch |
| A7 | Keine neuen Messwerte seit 30 min | warnung |
| A8 | Störungscode gesetzt | kritisch |
| A9 | Verdichter läuft, aber Vorlauf ≤ Rücklauf | kritisch |
| A10 | Stromverbrauch im Standby > 50 W über 6 h | hinweis |

Später: „Erwartungsmodell“ (Regression AZ/Leistung ~ Außentemperatur) aus den eigenen Daten lernen,
Abweichungen davon als Anomalie werten.
