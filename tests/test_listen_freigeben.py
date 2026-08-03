"""Die Listen-Ansicht lässt nichts im Dokument zurück.

Aus einem eingeschickten Absturzverlauf: Nach einem Blick in die
Einkaufslisten standen **4631 Elemente und 310 Bilder** im Dokument – und
blieben dort, auch nachdem längst Sammlung, Statistik und Einstellungen
drankamen. Fast eine Stunde unverändert, dann starb der Tab.

Zwei Stellen waren schuld: Eine **eingeklappte** Liste baute ihre Zeilen
trotzdem auf (sie standen nur auf `display: none`), und beim **Verlassen**
des Tabs wurde nichts geräumt – anders als bei der Sammlung, wo es das seit
2.9 gibt.

Gemessen an 310 Listenposten: 4631 → 973 Elemente, 310 → 4 Bilder.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def block(name: str) -> str:
    quelle = js()
    anfang = quelle.index(f"function {name}(")
    return quelle[anfang:quelle.index("\n}", anfang)]


# ------------------------------------------------------ Beim Verlassen räumen

def test_showtab_gibt_die_listen_frei():
    koerper = block("showTab")
    assert "listenFreigeben(name)" in koerper
    assert "sammlungFreigeben(name)" in koerper, "die Sammlung darf nicht verlieren"


def test_freigeben_raeumt_alle_drei_behaelter():
    """Wünsche, Einkaufslisten und Archiv liegen im selben Tab – bliebe einer
    stehen, wäre der Sockel nur teilweise weg."""
    koerper = block("listenFreigeben")
    for behaelter in ("lists-container", "archive-container", "wanted-list"):
        assert behaelter in koerper, f"{behaelter} wird nicht geräumt"


def test_freigeben_verschont_den_eigenen_tab():
    koerper = block("listenFreigeben")
    assert 'neuerTab === "lists"' in koerper and "return" in koerper


def test_die_behaelter_gibt_es_wirklich():
    """Ein Tippfehler im Namen räumte still gar nichts."""
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for behaelter in ("lists-container", "archive-container", "wanted-list"):
        assert f'id="{behaelter}"' in html


# --------------------------------------------- Eingeklappt heißt nicht gebaut

def test_eingeklappte_listen_bauen_keine_zeilen():
    quelle = js()
    assert "function listeOffen(" in quelle
    assert "listeOffen(l.id) ? l.items.map" in quelle, (
        "die Zeilen entstehen weiterhin unabhängig vom Zustand")


def test_das_umschalten_zeichnet_neu():
    """Die Zeilen entstehen beim Zeichnen, nicht beim Umschalten der Klasse –
    ohne Neuzeichnen bliebe eine aufgeklappte Liste leer."""
    quelle = js()
    # `.card-head` gibt es auch auf den Sammlungskarten – hier zählt die
    # Listenkarte, und die erkennt man am Umbenennen-Stift.
    i = quelle.index('if (ev.target.closest("[data-l-rename]")) return;')
    umfeld = quelle[i:i + 400]
    assert "renderLists(lists)" in umfeld
    assert 'classList.toggle("collapsed")' not in umfeld, (
        "die Klasse setzt jetzt das Zeichnen, nicht der Klick")


def test_der_gemerkte_zustand_bleibt_derselbe_schluessel():
    """Sonst stünden alle Listen nach dem Update wieder offen."""
    quelle = js()
    assert quelle.count('"bf_listcard_"') >= 2
    assert re.search(r'localStorage\.getItem\("bf_listcard_" \+ lid\) === "open"',
                     quelle)
