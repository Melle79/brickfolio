"""Die Artikelzeilen im Katalog – warum man die Figuren nicht auseinanderhielt.

**Der Name ist das, woran man die Figur erkennt, und er war zu drei Vierteln
weg.** Am 24.09.2026 auf einem Telefon nachgemessen (375 px, 80 Zeilen):
162 px für den Namen, **74 % abgeschnitten**, und **14 Zeilenpaare sahen
gleich aus**. Das ist kein Schönheitsfehler, sondern Unbrauchbarkeit:

    Luke Skywalker - Pilot Suit, … Dark Gray Hips, Yellow Head
    Luke Skywalker - Pilot Suit, … Dark Bluish Gray Hips, Yellow Head
              beide sichtbar als →  „Luke Skywalker - Pilot Suit"

BrickLink-Namen tragen die Identität vorn und das Unterscheidungsmerkmal
hinten – abgeschnitten wird also genau der Teil, der zählt. In der Mitte zu
kürzen half kaum (14 → 13 gleiche Paare): Die Namen teilen sich Kopf *und*
Schwanz.

Drei Schritte haben es gelöst, gemessen an denselben 80 Zeilen:

    einzeilig, 162 px  →  23 % ganz lesbar
    zweizeilig         →  57 %
    + Merkzeichen vom Zeilenende an den Daumennagel (196 px)  →  75 %
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(r"(?:async )?function %s\([^)]*\) \{.*?\n\}\n" % name,
                  js(), re.S)
    assert m, "%s nicht gefunden" % name
    return m.group(0)


def _regel(wahl: str) -> str:
    m = re.search(re.escape(wahl) + r"\s*\{([^}]*)\}", css(), re.S)
    assert m, "%s nicht gefunden" % wahl
    return m.group(1)


# ---------------------------------------------------- der Name

def test_der_name_darf_umbrechen():
    r = _regel(".kat-name")
    assert "-webkit-line-clamp: 2" in r
    assert "white-space: nowrap" not in r, (
        "eine Zeile war die Ursache, nicht die Lösung")


def test_zwei_zeilen_nicht_beliebig_viele():
    """Ohne Deckel zöge ein langer Name die Zeile auf vier Zeilen auf – bei
    1.663 Einträgen wäre das ein Vielfaches an Scrollweg."""
    assert "line-clamp: 2" in _regel(".kat-name")


# ---------------------------------------------------- die Fläche

def test_die_artikel_stehen_auf_einer_karte():
    r = _regel(".kat-gruppe")
    assert "background: var(--card)" in r
    assert "border: 2px solid var(--ink)" in r


def test_die_blocknummer_steht_zwischen_den_karten():
    """Sie gliedert, sie gehört nicht zu den Artikeln. Innerhalb der weißen
    Karte wäre sie eine Zeile wie jede andere; auf der grauen Fläche trennt
    sie. Darum bekommt **jeder Block seine eigene Karte** – erkennbar
    daran, dass die Nummer neben `.kat-gruppe` eingehängt wird, nicht
    hinein."""
    f = _fn("katNachschub")
    i_block = f.index("kat-block")
    i_gruppe = f.index('<div class="kat-gruppe"></div>`', i_block)
    assert i_gruppe > i_block, "die Karte beginnt nach der Nummer"
    assert 'liste.insertAdjacentHTML("beforeend",\n        `<div class="kat-block"' in f


def test_die_karte_wird_kein_scrollbereich():
    """**`overflow: hidden` wäre hier eine Falle.** Es macht aus der Karte
    einen eigenen Scrollbereich, und die Blocknummern (`position: sticky`)
    klebten dann an ihr statt am Bildschirmrand – sie blieben einfach
    stehen, wo sie gerade waren."""
    assert "overflow" not in _regel(".kat-gruppe")
    assert "position: sticky" in _regel(".kat-block"), (
        "wenn das wegfällt, ist dieser Test gegenstandslos"
    )


def test_die_karte_polstert_nicht_selbst():
    """Mit 10 px innen schrumpfte das Namensfeld von 162 auf 138 px – der
    Gewinn aus dem Umbruch fiel von 57 % auf 50 % zurück. Der Abstand steht
    stattdessen in der Zeile, die Trennstriche laufen durch."""
    assert "padding-left: 8px" in css()
    assert "padding" not in _regel(".kat-gruppe")


def test_der_letzte_strich_faellt_weg():
    """Sonst liefe er durch die runde Ecke der Karte."""
    assert ".kat-gruppe .kat-zeile:last-child { border-bottom: 0; }" in css()


def test_eine_leere_karte_zeigt_sich_nicht():
    """Beim Nachschub entsteht die Karte, bevor die Zeilen darin stehen –
    ein leerer weißer Streifen wäre sonst kurz zu sehen."""
    assert ".kat-gruppe:empty { display: none; }" in css()


# ---------------------------------------------------- das Merken

def test_in_der_zeile_steht_kein_merkknopf_mehr():
    """Er kostete 46 px – und der Name braucht sie dringender. Gemerkt wird
    selten, angesehen ständig."""
    f = _fn("katZeile")
    assert 'data-marke="wunsch"' not in f
    assert 'data-marke="habe"' in f, "die andere Marke bleibt, wo sie war"


def test_das_zeichen_sitzt_am_daumennagel():
    f = _fn("katZeile")
    assert "katStern(e.wunsch)" in f
    assert "kat-bildfeld" in f
    assert "position: relative" in _regel(".kat-bildfeld"), (
        "ohne das säße es irgendwo"
    )


def test_es_ist_ein_stern_kein_herz():
    """**Ein Zeichen für eine Liste.** Der Katalog war die einzige Stelle
    mit einem Herz; die Wunschliste trägt einen Stern im Reiter, und beim
    Scannen heißt es „☆ Merken"."""
    assert "\\u2605" in _fn("katStern")
    assert "\\u2665" not in js(), "nirgends mehr ein Herz fürs Merken"
    assert "katHerz" not in js()


def test_das_zeichen_ist_kein_knopf():
    f = _fn("katStern")
    assert "<button" not in f
    assert "aria-label" in f, "als reines Zeichen braucht es eine Ansage"


# ---------------------------------------------------- die Verdrahtung

def test_geschaltet_wird_aus_den_daten():
    """**Das war die eigentliche Gefahr an dieser Änderung.**

    `katMarkeUmlegen` nahm früher den *Knopf aus der Zeile* entgegen und las
    Marke und Zustand an ihm ab. Das Popup hatte deshalb keinen eigenen Weg:
    Es suchte den passenden Knopf in der Liste und klickte ihn. Nimmt man das
    Herz aus der Zeile, findet es nichts mehr – und `if (knopf)` hätte den
    Fall **kommentarlos verschluckt**. „Merken" wäre wirkungslos geworden,
    ohne eine einzige Fehlermeldung.
    """
    assert re.search(r"async function katMarkeUmlegen\(nr, marke, an\)", js())
    f = _fn("katMarkeUmlegen")
    assert "knopf" not in f


def test_das_popup_schaltet_selbst():
    m = re.search(r"function katDetail\(e\) \{.*?\n\}\n", js(), re.S)
    assert m
    f = m.group(0)
    assert "katMarkeUmlegen(e.item_no, marke, an)" in f
    assert '.kat-marke[data-marke=' not in f, (
        "nicht wieder über einen Knopf in der Liste")


def test_ein_fehlschlag_nimmt_die_anzeige_zurueck():
    """Erst zeigen, dann fragen – aber nur, wenn es auch hält."""
    f = _fn("katMarkeUmlegen")
    assert "const vorher = {" in f and "Object.assign(eintrag, vorher)" in f


def test_die_zeile_wird_aus_dem_eintrag_beschriftet():
    f = _fn("katZeileZeichnen")
    for teil in ("kat-marke", "kat-anzahl", "kat-wunsch"):
        assert teil in f, "%s bliebe sonst stehen" % teil
