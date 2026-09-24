"""Niemand benutzt ein `meta`, das es in seiner Funktion nicht gibt.

**Derselbe Fehler, zweimal im selben Commit.** 2.86.5 brachte `detailVon`
und setzte `enrichSuggestions(items, meta.detailVon || 0)` an zwei Stellen:
in `renderSuggestions`, wo `meta` ein Parameter ist – und in
`renderScanResults`, wo es das nicht gibt.

Die zweite Stelle war die teurere. Die Ausnahme flog **vor** dem
Verdrahten der Knöpfe:

    enrichSuggestions(items, meta.detailVon || 0);   <- hier knallt es
    wireWantButtons(box, items, …);
    …
    box.querySelectorAll("[data-add]").forEach(…);   <- kommt nie an

Die Karte stand also vollständig da, „＋ Zur Sammlung" tat nichts, und im
Fehlerprotokoll stand nichts. Zwei Tage lang konnte niemand eine
gescannte Figur aufnehmen (22.–24.09.2026).

Ein Wortlaut-Test hätte das nicht gefunden – beide Zeilen sahen richtig
aus. Darum prüft dieser Test den **Geltungsbereich**.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def _ohne_beiwerk(q: str) -> str:
    """Kommentare und Zeichenketten ausblenden, Länge und Zeilen wahren.

    Ohne das zählte jedes `<meta …>` in einer HTML-Vorlage und jedes „meta"
    in einem Kommentar mit – und der Test meldete fünf Funktionen, von denen
    keine ein Problem hatte.
    """
    out, i, n = list(q), 0, len(q)
    while i < n:
        z = q[i]
        if z == "/" and i + 1 < n and q[i + 1] == "/":
            j = q.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif z == "/" and i + 1 < n and q[i + 1] == "*":
            j = q.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if q[k] != "\n":
                    out[k] = " "
            i = j
        elif z in "\"'`":
            j = i + 1
            while j < n:
                if q[j] == "\\":
                    j += 2
                    continue
                if q[j] == z:
                    j += 1
                    break
                j += 1
            for k in range(i, min(j, n)):
                if q[k] != "\n":
                    out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


def _funktionen(sauber: str):
    for m in re.finditer(r"^(?:async )?function (\w+)\(([^)]*)\) \{", sauber, re.M):
        tiefe, i = 1, m.end()
        while tiefe and i < len(sauber):
            if sauber[i] == "{":
                tiefe += 1
            elif sauber[i] == "}":
                tiefe -= 1
            i += 1
        yield m.group(1), m.group(2), sauber[m.end():i], m.start()


def test_kein_freies_meta():
    quelle = (FRONTEND / "app.js").read_text(encoding="utf-8")
    sauber = _ohne_beiwerk(quelle)
    frei = []
    for name, args, rumpf, pos in _funktionen(sauber):
        if not re.search(r"(?<![\w.])meta\b", rumpf):
            continue
        if re.search(r"(?<![\w.])meta\b", args):
            continue
        if re.search(r"(?:const|let|var)\s+meta\b", rumpf):
            continue
        frei.append("%s (Zeile %d)" % (name, quelle[:pos].count("\n") + 1))
    assert not frei, "benutzen ein `meta`, das es dort nicht gibt: " + ", ".join(frei)


def test_der_scan_reicht_kein_meta_durch():
    """Die Scan-Ergebnisse kommen in einem Stück – es gibt keine zweite
    Seite und damit nichts, ab dem die teuren Abrufe ansetzen müssten."""
    quelle = (FRONTEND / "app.js").read_text(encoding="utf-8")
    m = re.search(r"function renderScanResults\(items\) \{.*?\n\}\n", quelle, re.S)
    assert m
    assert "enrichSuggestions(items);" in m.group(0)
