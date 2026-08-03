"""Das Themenfeld steht nur da, wenn die Automatik nichts fand.

Als es kam (1.90.0), standen Teile reihenweise unter „Ohne Thema": BrickLink
sortiert sie nach **Form** („Brick, Modified"), nicht nach Thema. Seit das
Thema über die Zweitnummer des Teils gefunden wird, ist der Normalfall
erledigt – dann standen dort Eingabefeld und Knopf für etwas, das längst
richtig ausgefüllt war.

Ganz weg darf es trotzdem nicht: Falsch zugeordnet wird auch mal etwas, und
ohne einen Weg dahin bliebe es falsch.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def test_mit_thema_steht_nur_das_thema_da():
    quelle = js()
    assert 'data-thema-fest${it.theme ? "" : " hidden"}' in quelle
    assert 'data-thema-feld${it.theme ? " hidden" : ""}' in quelle


def test_der_stift_holt_das_feld_zurueck():
    quelle = js()
    assert "data-thema-aendern" in quelle
    stelle = quelle.index("[data-thema-aendern]")
    umfeld = quelle[stelle:stelle + 300]
    assert "zeigen(true)" in umfeld
    assert "themaEl.focus()" in umfeld, "sonst muss man erst hineinklicken"


def test_nach_dem_setzen_geht_es_wieder_zu():
    """Sonst bliebe das Feld offen stehen, obwohl das Thema jetzt passt."""
    quelle = js()
    stelle = quelle.index("const setzen = async ()")
    umfeld = quelle[stelle:stelle + 1200]
    assert "wertEl.textContent = wert" in umfeld, "der Text muss mitziehen"
    assert "zeigen(false)" in umfeld


def test_ohne_thema_bleibt_das_feld_offen():
    """`zeigen` hängt an `item.theme`, nicht am Knopfdruck: Wer das Thema
    leert, steht ohne – dann gehört das Feld sichtbar."""
    quelle = js()
    stelle = quelle.index("const zeigen = (bearbeiten)")
    umfeld = quelle[stelle:stelle + 260]
    assert "!item.theme" in umfeld
    assert "!!item.theme" in umfeld


def test_ausgeblendet_heisst_ausgeblendet():
    """`display: flex` aus dem eigenen Blatt schlägt das `display: none`, das
    der Browser für `hidden` mitbringt – Autorenregeln gehen vor. Ohne diese
    Regel bliebe die Zeile trotz `hidden` stehen."""
    assert re.search(r"\.detail-row\[hidden\]\s*\{\s*display:\s*none", css())
