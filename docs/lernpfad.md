# Lernpfad: Mit mehreren Copilot-Agenten eine App bauen

Jede Stufe bringt die App ein Stück weiter **und** bringt dir eine neue Agenten-Technik bei.
Voraussetzungen: GitHub-Konto mit Copilot (für den Cloud-Agenten mind. Pro), VS Code mit GitHub-Copilot-Erweiterung, Git, Python 3.11+.

> Copilot ändert sich schnell. Wenn ein Menüpunkt anders heißt: in der GitHub-Doku nach „Copilot coding agent“ und „custom agents“ suchen.

---

## Stufe 0 – Projekt aufsetzen (30 min)
1. Neues **privates** Repo auf GitHub anlegen, z. B. `wp-analyse`.
2. Diesen Ordner hineinkopieren, committen, pushen.
3. Lokal: `pip install -e ".[dev]"`, dann `python -m wpanalyse.demo` und `pytest`.

**Gelernt:** Die Basis steht – Regeln (`copilot-instructions.md`) und Agenten (`.github/agents/`) liegen im Repo und gelten automatisch.

## Stufe 1 – Agent Mode in VS Code (1 h)
1. Copilot-Chat öffnen, Modus **Agent** wählen.
2. Prompt: *„Lies docs/fachwissen.md und ergänze in src/wpanalyse/analyse/ ein Modul `spreizung.py` nach dem Muster von `taktung.py`, inkl. Test.“*
3. Beobachte: Welche Dateien liest er? Welche Befehle führt er aus? Bestätige oder lehne Schritte ab.
4. Prüfe das Ergebnis selbst, bevor du committest.

**Gelernt:** Ein Agent plant, ändert mehrere Dateien und testet selbst. Du bist Reviewer.

## Stufe 2 – Instruktionen wirken lassen (30 min)
1. Gleiche Aufgabe nochmal ohne Hinweis auf `fachwissen.md` – hält er sich trotzdem an die Regeln (Einheiten im Namen, Schwellwerte in config)?
2. Ändere eine Regel in `copilot-instructions.md` und schau, wie sich die Antwort ändert.

**Gelernt:** Gute Projektregeln sind der größte Hebel für Qualität.

## Stufe 3 – Custom Agents (1 h)
1. Im Chat den Agenten **architekt** auswählen (Agent-Auswahl im Chatfenster).
2. Prompt: *„Zerlege Issue 4 aus docs/backlog.md in Teilaufgaben.“*
3. Danach **analyst** eine Teilaufgabe umsetzen lassen, dann **reviewer** den Diff prüfen lassen.

**Gelernt:** Rollen trennen = bessere Ergebnisse. Jeder Agent hat einen klaren Auftrag und klare Grenzen.

## Stufe 4 – Coding Agent in der Cloud (1–2 h)
1. Issues aus `docs/backlog.md` auf GitHub anlegen (Text kopieren).
2. Einem Issue **Copilot als Assignee** zuweisen (optional mit Custom Agent, z. B. `tester`).
3. Der Agent arbeitet im Hintergrund und öffnet einen **Draft-PR**. Fortschritt im PR bzw. in der Agenten-Übersicht verfolgen.
4. Im PR kommentieren (*„@copilot bitte noch Test für Datenlücken ergänzen“*) – der Agent arbeitet nach.

**Gelernt:** Aufgaben delegieren statt selbst tippen. Gute Issues = gute PRs.

## Stufe 5 – Mehrere Agenten parallel (2–3 h)
1. Drei Issues, die **keine gemeinsamen Dateien** haben, gleichzeitig vergeben – z. B. Issue 3 (analyst), 5 (tester), 6 (alarm).
2. Jeden PR mit dem **reviewer**-Agenten prüfen lassen, danach selbst entscheiden und mergen.
3. Optional: dasselbe Issue an zwei verschiedene Agenten (z. B. Copilot und Claude über Agent HQ) geben und Ergebnisse vergleichen.

**Gelernt:** Parallel arbeiten klappt nur mit sauber geschnittenen Aufgaben. Du bist der „Teamleiter“, der Aufgaben verteilt und mergt.

## Stufe 6 – Echtbetrieb
1. Issue 2 (Adapter für deine echte WP) mit dem **datensammler** umsetzen.
2. Ein paar Wochen Daten sammeln, Schwellwerte in `config.py` an dein Haus anpassen.
3. Neue Ideen immer erst durch den **architekt** in Issues zerlegen lassen.

---

## Faustregeln für Agenten-Arbeit
- **Kleine Issues** (ein PR, wenige Dateien, klares Akzeptanzkriterium).
- **Tests zuerst definieren** – sie sind die Messlatte für den Agenten.
- **Nie ungeprüft mergen**: Du verantwortest den Code.
- **Kontext ins Repo** statt in den Chat: was in `docs/` steht, wissen alle Agenten.
