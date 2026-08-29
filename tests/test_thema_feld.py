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


def test_das_thema_steht_im_kopf_das_feld_bleibt_zu():
    """Seit 2.72.0 steht das Thema oben im Kopf des Steckbriefs.

    Das Eingabefeld startet geschlossen – auch ohne Thema. Dort steht dann
    „Thema setzen" als Einladung, und der Stift holt das Feld. Vorher stand
    bei jedem Eintrag ohne Thema ein offenes Feld im Weg.
    """
    quelle = js()
    assert 'data-thema-feld hidden' in quelle
    assert "themaKopfzeile(item)" in quelle
    assert 'tr("Thema setzen")' in quelle


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


def test_ohne_thema_steht_die_einladung_da():
    """Wer das Thema leert, steht ohne – dann gehört dort nicht nichts,
    sondern der Weg zurück. `zeigen` weicht seit 2.72.0 nur noch beim
    Bearbeiten, und der Text fällt auf die Einladung zurück."""
    quelle = js()
    stelle = quelle.index("const zeigen = (bearbeiten)")
    umfeld = quelle[stelle:stelle + 260]
    assert "festRow.hidden = bearbeiten;" in umfeld
    assert "feldRow.hidden = !bearbeiten;" in umfeld
    stelle2 = quelle.index("const setzen = async ()")
    assert 'wert || tr("Thema setzen")' in quelle[stelle2:stelle2 + 1200]


def test_ausgeblendet_heisst_ausgeblendet():
    """`display: flex` aus dem eigenen Blatt schlägt das `display: none`, das
    der Browser für `hidden` mitbringt – Autorenregeln gehen vor. Ohne diese
    Regel bliebe die Zeile trotz `hidden` stehen."""
    assert re.search(r"\.detail-row\[hidden\]\s*\{\s*display:\s*none", css())
