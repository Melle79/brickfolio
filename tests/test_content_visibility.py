"""`content-visibility: auto` ist ausgebaut – als Versuch.

Von 40 Absturz-Dumps auf Svens Rechner sind alle 40 auf Brickfolio; keine
andere Seite. Es ist ein Chromium-Fehler (ein absichtlicher Abbruch,
`EXC_BREAKPOINT`, in Edge 151 wie in Chrome 152), aber etwas an dieser
Seite löst ihn aus. `content-visibility` war das Ungewöhnlichste, was die
App tut, es saß in der Sammlung, und es griff ineinander mit
`position: sticky`, dem Bildbeobachter und dem Bildladen auf denselben
Elementen.

Kommen die Abstürze weiter, gehört die Zeile zurück. Bis dahin wacht
dieser Test darüber, dass sie nicht versehentlich wiederkehrt.
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "style.css"


def _regeln(text: str) -> str:
    """Nur der wirksame Teil – Kommentare erklären den Ausbau ja gerade."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_content_visibility_ist_draussen():
    assert "content-visibility" not in _regeln(CSS.read_text())


def test_kein_verwaistes_contain_intrinsic_size():
    """Ohne `content-visibility` tut es nichts und stiftet nur Verwirrung."""
    assert "contain-intrinsic-size" not in _regeln(CSS.read_text())


def test_der_grund_steht_dabei():
    """Wer die Zeile vermisst, soll im Quelltext finden, warum sie fehlt –
    und woran zu erkennen wäre, dass sie zurück muss."""
    text = CSS.read_text()
    assert "content-visibility" in text, "Der Kommentar dazu fehlt"
    assert "EXC_BREAKPOINT" in text or "Chromium" in text
