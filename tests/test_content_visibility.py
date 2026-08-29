"""`content-visibility: auto` steht wieder auf den Sammlungskarten.

Es war am 29.08.2026 versuchsweise ausgebaut: Von 40 Absturz-Dumps auf
Svens Rechner sind alle 40 auf Brickfolio, und `content-visibility` ist
das Ungewöhnlichste, was diese Seite tut.

**Der Versuch ist gelaufen, das Ergebnis war negativ.** Der Bericht zu
2.70.0 führt drei weitere Abstürze, alle nach dem Ausbau. Die Zeile spart
dem Browser echte Arbeit (gemessen: statt 815 Hintergrundbildern beim
Öffnen nur noch 16) und steht deshalb wieder da.

Dieser Test hält beides fest: dass sie da ist, und warum sie nicht noch
einmal als Verdächtige herhalten muss.
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "style.css"


def _regeln(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_content_visibility_steht_auf_den_sammlungskarten():
    regeln = _regeln(CSS.read_text())
    assert "content-visibility: auto" in regeln
    assert "#collection-list .card { content-visibility: auto;" in regeln


def test_die_hoehenangabe_gehoert_dazu():
    """Ohne `contain-intrinsic-size` springt die Bildlaufleiste beim
    Scrollen, weil der Browser die Höhe nicht kennt."""
    regeln = _regeln(CSS.read_text())
    assert "contain-intrinsic-size: auto 104px" in regeln   # Liste
    assert "contain-intrinsic-size: auto 236px" in regeln   # Raster
    assert "contain-intrinsic-size: auto 132px" in regeln   # kompakt


def test_das_ergebnis_des_versuchs_steht_dabei():
    """Damit niemand – ich eingeschlossen – denselben Versuch noch einmal
    macht."""
    text = CSS.read_text()
    assert "wieder eingebaut" in text
    assert "2.70.0" in text and "drei" in text
