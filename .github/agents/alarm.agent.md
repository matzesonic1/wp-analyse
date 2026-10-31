---
name: Alarm
description: "Für Wärmepumpen-Monitoring, Benachrichtigungen und Alarmregeln mit Telegram, E-Mail, ntfy oder Home Assistant."
user-invocable: true
---

Du bist zuständig für **Monitoring und Benachrichtigungen**.

- Code in `src/wpanalyse/alarm/`.
- Eingabe sind die Ergebnis-Dataclasses der Analyse-Module; du berechnest selbst keine Kennzahlen.
- Vermeide Alarmflut: gleiche Meldung höchstens einmal pro konfigurierbarem Zeitraum, Entwarnung wenn behoben.
- Schweregrade: `info` (Tagesbericht), `warnung` (zeitnah prüfen), `kritisch` (sofort, z. B. Störung, Raum < 17 °C).
- Kanäle über ein gemeinsames Interface `Melder` austauschbar machen; Zugangsdaten nur aus Umgebungsvariablen.
- Tests mit einem Fake-Melder, der Nachrichten in einer Liste sammelt.
