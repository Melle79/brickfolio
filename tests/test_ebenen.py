"""Was oben liegt, muss oben liegen.

Eine Rückfrage, die hinter dem Fenster erscheint, aus dem sie kommt, ist
schlimmer als keine: Man sieht sie nicht, und die Aktion scheint zu hängen.
Genau das passierte bei „Mein Foto entfernen?" – die Frage lag unter der
Großansicht.
"""
import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[1] / "frontend" / "style.css"


def ebene(auswahl: str) -> int:
    """z-index einer Regel aus der Datei lesen."""
    text = CSS.read_text(encoding="utf-8")
    stelle = text.index(auswahl + " {") if auswahl + " {" in text \
        else text.index(auswahl + "{")
    block = text[stelle:text.index("}", stelle)]
    treffer = re.search(r"z-index:\s*(\d+)", block)
    assert treffer, f"{auswahl} hat keinen z-index"
    return int(treffer.group(1))


def test_rueckfrage_liegt_ueber_der_grossansicht():
    """Der eigentliche Fehler: Aus der Großansicht heraus wird gefragt."""
    assert ebene(".card-modal-overlay.stacked") > ebene(".lightbox")


def test_rueckfrage_liegt_ueber_dem_gewoehnlichen_fenster():
    assert ebene(".card-modal-overlay.stacked") > ebene(".card-modal-overlay")


def test_toast_bleibt_ganz_oben():
    """Sonst bliebe die Antwort auf eine Aktion dort unsichtbar, wo sie
    ausgelöst wurde."""
    oben = ebene(".toast")
    for andere in (".lightbox", ".card-modal-overlay",
                   ".card-modal-overlay.stacked"):
        assert oben > ebene(andere), andere


@pytest.mark.parametrize("auswahl", [".lightbox", ".card-modal-overlay",
                                     ".card-modal-overlay.stacked", ".toast"])
def test_jede_ebene_ist_ueberhaupt_gesetzt(auswahl):
    assert ebene(auswahl) > 0
