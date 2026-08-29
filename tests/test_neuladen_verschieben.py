"""Ein Neustart des Servers darf keine laufende Arbeit wegwerfen.

Am 29.08.2026 im LEGO-Museum: Sven scannte, und die App lud sich mehrmals
von selbst neu. Ursache waren elf Update-Läufe an diesem Tag – jeder
Neustart lässt jede offene Seite neu laden, und das ist auch richtig. Falsch
war der Zeitpunkt: Foto, erkannte Figuren und gezogene Rahmen sind danach
weg.
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def _fn(name: str) -> str:
    js = APP_JS.read_text()
    m = re.search(r"function %s\([^)]*\) \{.*?\n\}\n" % name, js, re.S)
    assert m, "%s nicht gefunden" % name
    return m.group(0)


def test_neuladen_fragt_erst_ob_arbeit_laeuft():
    f = _fn("neuLadenMit")
    assert "arbeitLaeuft()" in f
    # Und zwar **vor** dem Neuladen, nicht danach.
    assert f.index("arbeitLaeuft()") < f.index("location.reload()")


def test_was_als_arbeit_gilt():
    """Vier Dinge, die ein Neuladen zerstört."""
    f = _fn("arbeitLaeuft")
    assert "reihumLaeuft" in f, "laufende Reihum-Suche"
    assert "scan-preview" in f and "scan-results" in f, "Foto mit Treffern"
    assert "card-modal" in f and "kat-modal" in f, "offene Fenster"
    assert "lightbox" in f, "offene Großansicht"


def test_verschobenes_neuladen_wird_nachgeholt():
    """Sonst bliebe die Seite für immer auf der alten Fassung."""
    js = APP_JS.read_text()
    f = _fn("neuladenNachholen")
    assert "neuladenAusstehend" in f and "neuLadenMit(" in f
    # An jedem Punkt, an dem eine Arbeit endet.
    for stelle in ("function showTab(", "function closeGallery(",
                   "function closeCardModal("):
        anfang = js.index(stelle)
        assert "neuladenNachholen()" in js[anfang:anfang + 1800], stelle


def test_der_anwender_erfaehrt_davon():
    """Eine Seite, die heimlich auf eine Gelegenheit wartet, ist schlechter
    als eine, die es sagt."""
    f = _fn("neuLadenMit")
    assert "showUpdateBar(true" in f
