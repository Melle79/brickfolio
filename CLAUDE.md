# Arbeiten an Brickfolio

Selbstgehostete PWA für LEGO-Sammlungen: FastAPI + SQLite im Rücken,
Vanilla-JS im Browser. **Kein Bauschritt**, keine Abhängigkeiten im Frontend –
`frontend/app.js` wird so ausgeliefert, wie sie im Repo steht.

## Sprache

Alles auf Deutsch: Oberfläche, Kommentare, Commit-Texte, Changelog, Handbuch.
Die deutschen Zeichenketten **sind** die Übersetzungsschlüssel;
`frontend/i18n/en.json` bildet sie ab (sortiert, `indent=1`). Ein Test schlägt
an, sobald ein Schlüssel dort keine Entsprechung mehr in der Oberfläche hat.

Kommentare erklären das **Warum**, nicht das Was – und besonders das, was ohne
Erklärung wie ein Fehler aussieht. Wo eine Entscheidung aus einem konkreten
Vorfall stammt, gehört der Vorfall dazu.

## Prüfen statt behaupten

Der Quelltext ist kein Beweis. Was am laufenden Programm geprüft werden kann,
wird dort geprüft:

    DB_PATH=… SECRET_KEY_FILE=… UPLOAD_DIR=… FRONTEND_DIR=./frontend \
      .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8400   # aus backend/

**Die Cache-Falle:** Die Dateien gehen mit `immutable` raus. Nach einer
Änderung an JS oder CSS zeigt der Browser weiter die alte Fassung, solange
`APP_VERSION` gleich bleibt – entweder Version hochsetzen oder auf einem
**anderen Port** starten, dort ist der Zwischenspeicher leer. Das hat schon
mehrfach eigene Testartefakte wie Fehler aussehen lassen.

**`node --check frontend/app.js`** gehört zu jeder Frontend-Änderung. Die
Python-Tests lesen die Datei, sie führen sie nicht aus – ein Syntaxfehler
kommt dort nie an, zerlegt die App aber beim Laden.

## Tests

`pytest` aus dem Projektstamm. Ein neuer Test beschreibt im Docstring den
**Vorfall**, aus dem er entstanden ist, nicht die Funktion, die er aufruft.
Und er muss ohne die Korrektur durchfallen – sonst prüft er nichts:

    git stash push backend/main.py && pytest tests/test_neu.py; git stash pop

## Nach jeder Änderung

1. `APP_VERSION` in `backend/core.py` hochsetzen
2. `CHANGELOG.md` – was war kaputt, was ist jetzt anders, **warum**
3. Handbuch (`docs/HANDBUCH.md`) nachziehen, wenn sich Bedienung ändert
4. Übersetzungen ergänzen
5. Commit, Tag, Release

Ohne Versionssprung sieht niemand die Änderung – siehe Cache-Falle.

## Was leicht schiefgeht

- **`requests.HTTPError` erbt von `RequestException`.** Ein 404 fällt sonst in
  den Zweig „Dienst nicht erreichbar" und wird als Ausfall gemeldet.
- **Deutsche Anführungszeichen** in Python-Zeichenketten zerlegen sie.
- **`display: flex`** schlägt `[hidden] { display: none }` des Browsers –
  versteckte Zeilen brauchen eine eigene Regel.
- **BrickLink-Nummern** sind nicht die von Rebrickable. Preise gehen über die
  BrickLink-Nummer, sonst kommt nichts zurück.
