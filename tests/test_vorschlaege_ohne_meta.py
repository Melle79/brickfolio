"""`renderSuggestions` ohne zweites Argument – drei Wege, ein Absturz.

**Aus der App gemeldet (24.09.2026, 2.88.30):**
`TypeError: Cannot read properties of undefined (reading 'detailVon')`,
aus `runCatalogSearch` heraus.

Die Funktion nimmt `items` und ein freiwilliges `meta`. Drei der vier
Aufrufer haben keines: die BrickLink-Nummernsuche (zwei Stellen) und die
Scan-Kandidaten. Im Rumpf war eine Stelle abgesichert (`meta && meta.count`)
und eine nicht (`meta.detailVon`).

**Warum es drei Monate unentdeckt blieb:** Der dritte Aufrufer steht in
einem `try`/`catch`, das jede Ausnahme in einen Hinweistext verwandelt. Dort
las man dann „Cannot read properties of undefined – der Eintrag behält die
Rebrickable-Nummer" und hielt es für eine Meldung des Dienstes. Gemeldet
wurde nichts.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def test_meta_ist_freiwillig():
    assert re.search(r"function renderSuggestions\(items, meta = \{\}\)", js())


def _argumente(quelle, name):
    """Die Argumentlisten aller Aufrufe – mit Klammerpaarung.

    Ein Muster wie `\\([^,)]+\\)` reicht nicht: Ein Aufruf kann selbst
    Kommas und Klammern enthalten (`renderSuggestions(xs.map((c) => …))`),
    und genau der wäre dann übersehen worden.
    """
    listen = []
    for m in re.finditer(r"(?<![\w.])%s\(" % name, quelle):
        if quelle[:m.start()].rstrip().endswith("function"):
            continue                       # die Vereinbarung, kein Aufruf
        tiefe, i = 1, m.end()
        while tiefe and i < len(quelle):
            if quelle[i] in "([{":
                tiefe += 1
            elif quelle[i] in ")]}":
                tiefe -= 1
            i += 1
        listen.append(quelle[m.end():i - 1])
    return listen


def _hat_zweites_argument(arg):
    tiefe = 0
    for z in arg:
        if z in "([{":
            tiefe += 1
        elif z in ")]}":
            tiefe -= 1
        elif z == "," and tiefe == 0:
            return True
    return False


def test_es_gibt_aufrufer_ohne_meta():
    """Die Absicherung ist keine Vorsichtsmaßnahme auf Verdacht – ohne sie
    stürzen genau diese Aufrufe ab."""
    listen = _argumente(js(), "renderSuggestions")
    assert listen, "keine Aufrufe gefunden – prüft dieser Test noch etwas?"
    ohne = [a for a in listen if not _hat_zweites_argument(a)]
    assert len(ohne) >= 3, [l[:60] for l in listen]


def test_ein_programmfehler_wird_gemeldet_statt_angezeigt():
    """Der Fangblock der Nummernsuche hat den Fehler versteckt. Ein
    `TypeError` ist kein Netzwerkfehler und gehört ins Protokoll."""
    i = js().index("der Eintrag behält die Rebrickable-Nummer.\";\n  }\n}")
    block = js()[i - 700:i]
    assert "e instanceof TypeError" in block
    assert "reportError(" in block
