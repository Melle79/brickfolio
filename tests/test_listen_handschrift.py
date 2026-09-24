"""Wunschliste und Einkaufsliste in derselben Sprache wie der Scan.

Am 24.09.2026 von Sven nachgezeigt: „Wunschliste und Einkaufsliste
ebenso" – dort standen noch vier gleich große Knöpfe im Raster, zwei
umrandete Zustandsknöpfe (einer gelb), ein grüner ✓-Balken über die volle
Breite und „Liste löschen" über die volle Breite.

Das Muster ist überall dasselbe: eine breite Hauptsache, Löschen und
Abbrechen als rotes Zeichen, die Wege nach draußen als Verweise, eine Wahl
als Pille.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(r"(?:async )?function %s\([^)]*\) \{.*?\n\}\n" % name, js(), re.S)
    assert m, name
    return m.group(0)


# ---------------------------------------------------- Wunschliste

def test_wunschkarte_hat_eine_hauptsache():
    q = js()
    assert '<button class="mini-btn add" data-buy>${esc(tr("✔ Gekauft!"))}</button>' in q
    assert 'class="mini-btn zeichen loesch" data-del' in q
    assert '<button class="mini-btn danger" data-del>Löschen</button>' not in q


def test_wunschkarte_verweise_sind_text():
    q = js()
    start = q.index("data-buy>")
    teil = q[start:start + 1600]
    assert 'class="mini-btn link"' not in teil, "Preisverlauf/BrickLink waren Knöpfe"
    assert "karte-weiter" in teil


def test_gekauft_als_ist_die_zustandszeile():
    q = js()
    assert 'actions.className = "zust-reihe";' in q
    assert 'class="mini-btn zust-abbruch" data-buy-cancel' in q
    assert "`In die Sammlung übernommen ✔ (" not in q, "Zuruf ohne Übersetzung"


# ---------------------------------------------------- Einkaufsliste

def test_einkaufsartikel_zustand_ist_eine_pille():
    f = _fn("listItemRow")
    assert 'class="erf-wahl" role="radiogroup"' in f
    assert "cond-mini" not in f
    assert 'data-ic="used" data-icid=' in f, "der Lauscher hängt an data-ic"


def test_einkaufsartikel_speichern_ist_klein():
    """Der ✓ zum Speichern des Einkaufspreises war ein grüner Balken über die
    volle Breite."""
    f = _fn("listItemRow")
    assert 'class="mini-btn add liste-speichern" data-ip-save=' in f
    assert 'style="flex:1;min-height:38px"' not in f


def test_einkaufsartikel_entfernen_ist_ein_rotes_quadrat():
    f = _fn("listItemRow")
    assert 'class="mini-btn zust-abbruch" data-i-del=' in f


def test_liste_loeschen_ist_ein_rotes_zeichen():
    q = js()
    assert 'class="mini-btn zust-abbruch loesch" data-l-del' in q
    assert '<button class="mini-btn danger" data-l-del>Liste löschen</button>' not in q
    assert ".liste-fuss .zust-abbruch {" in css()
