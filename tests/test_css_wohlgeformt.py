"""Das Stylesheet auf grobe Schnitzer prüfen.

Anlass: Beim Ausbau einer alten Lade-Anzeige wurde ein Block eine Zeile zu
früh aufgeschnitten – die Regel darüber verlor ihre schließende Klammer.
Der Browser schluckt so etwas still und wirft nur die Regeln weg, die er
nicht mehr zuordnen kann; hier fiel die Zentrierung der Sammlungsansicht
aus, ohne dass irgendein Test rot wurde.

Ein vollständiger CSS-Parser wäre dafür zu viel. Es reicht, das zu prüfen,
was beim Schneiden und Einfügen kaputtgeht: Klammern, die sich nicht
schließen, und Blöcke ohne Aufschrift.
"""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "style.css"


def _ohne_kommentare(text: str) -> str:
    """Kommentare durch Leerzeichen ersetzen – Zeilennummern bleiben so heil."""
    return re.sub(
        r"/\*.*?\*/",
        lambda t: re.sub(r"[^\n]", " ", t.group(0)),
        text,
        flags=re.S,
    )


def test_klammern_gehen_auf_und_wieder_zu():
    roh = _ohne_kommentare(CSS.read_text(encoding="utf-8"))
    tiefe = 0
    for nr, zeile in enumerate(roh.splitlines(), 1):
        for zeichen in zeile:
            if zeichen == "{":
                tiefe += 1
            elif zeichen == "}":
                tiefe -= 1
                assert tiefe >= 0, f"style.css:{nr}: eine Klammer zu viel"
        # Tiefer als zwei kommt nur in verschachtelten @-Regeln vor;
        # alles darüber ist fast sicher eine vergessene Klammer.
        assert tiefe <= 2, f"style.css:{nr}: Block nicht geschlossen"
    assert tiefe == 0, "style.css: am Ende ist ein Block noch offen"


def test_jeder_block_hat_eine_aufschrift():
    """Nach einem `}` darf kein `{` ohne Auswahl dazwischen folgen."""
    roh = _ohne_kommentare(CSS.read_text(encoding="utf-8"))
    for treffer in re.finditer(r"}\s*{", roh):
        nr = roh.count("\n", 0, treffer.start()) + 1
        raise AssertionError(f"style.css:{nr}: Block ohne Selektor")


def test_keine_verwaisten_klassen_mehr():
    """Regeln, die niemand mehr benutzt, sollen nicht liegenbleiben.

    Stichprobe auf die eine Klasse, die beim Umbau auf die Wellen-Anzeige
    verschwunden ist: Taucht `spinner-brick` irgendwo wieder auf, wurde
    entweder die alte Anzeige zurückgeholt oder ein Rest übersehen.
    """
    wurzel = CSS.parent.parent
    for ordner in ("frontend", "backend"):
        for datei in (wurzel / ordner).rglob("*"):
            if not datei.is_file() or datei.suffix not in {".css", ".js", ".html", ".py"}:
                continue
            text = datei.read_text(encoding="utf-8", errors="ignore")
            assert "spinner-brick" not in text, f"{datei.name}: alte Lade-Anzeige"
