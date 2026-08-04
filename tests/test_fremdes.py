"""Wer sitzt sonst noch in dieser Seite?

„Script error." sagt: Es lief fremder Code. Es sagt nicht, **welcher** – und
genau daran hängt die Frage, die seit Wochen offen ist. Der Tab stirbt bei
970 Elementen genauso wie bei 14.585, im Hintergrund wie im Vordergrund;
kein Maß der App erklärt das. Was jedes Mal dabei ist, ist fremder Code im
selben Renderer-Prozess – stürzt der ab, nimmt er die Seite mit, ganz
gleich wie klein sie ist.

Sichtbar ist der Teil, der im Dokument landet: eingehängte Skripte,
Stilblätter und Rahmen mit einer Erweiterungs-Adresse, dazu Elemente, die
jemand nachträglich an `<body>` gehängt hat.
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


def test_alle_gaengigen_erweiterungs_schemata():
    """Chrome, Firefox, Safari, Edge und Opera schreiben ihre Adressen
    verschieden. Fehlt eine, sieht man ausgerechnet dort nichts."""
    muster = re.search(r"const FREMD_SCHEMA = /([^/]+)/i", js())
    assert muster, "kein Muster für Erweiterungs-Adressen"
    for browser in ("chrome", "moz", "safari", "edge", "opera"):
        assert browser in muster.group(1), f"{browser} fehlt"


def test_gesucht_wird_in_skripten_stilen_und_rahmen():
    koerper = block("fremdeSpuren")
    for was in ("script[src]", "link[href]", "iframe[src]"):
        assert was in koerper, f"{was} wird nicht durchsucht"


def test_eigene_elemente_werden_vorher_gemerkt():
    """Ohne diesen Stichtag gälte alles unter <body> als fremd – auch die
    eigenen Ansichten. Das Merken muss **vor** der Diagnose laufen, weil
    die es sofort in ihre Startzeile schreibt."""
    quelle = js()
    assert "function eigeneKinderMerken()" in quelle
    i = quelle.index("eigeneKinderMerken();")
    j = quelle.index("diagStarten();", i - 400)
    assert i < j, "wird erst nach der Diagnose gemerkt"


def test_das_eigene_popup_gilt_nicht_als_fremd():
    """`card-modal` hängt die App selbst nachträglich an <body> – ohne
    Ausnahme meldete jeder geöffnete Artikel eine Erweiterung."""
    assert 'el.id === "card-modal"' in block("fremdeSpuren")


def test_der_fund_steht_im_fehlerbericht():
    quelle = js()
    i = quelle.index("istFremdfehler(ev.message")
    umfeld = quelle[i:i + 900]
    assert "fremdeSpuren()" in umfeld
    assert "Fremdes in dieser Seite:" in umfeld


def test_der_fund_steht_an_jedem_messpunkt():
    """Nicht nur in der Startzeile.

    In 2.19.0 stand er dort allein – und blieb leer. Das war kein Ergebnis,
    sondern ein Messfehler: Die Startzeile entsteht beim Laden, also
    **bevor** eine Erweiterung ihre Sachen einhängt. Bei den ausgewerteten
    Abstürzen gab es außerdem oft gar keinen Fehlereintrag, nur ein
    fehlendes Lebenszeichen – dann zählt allein der letzte Messpunkt.
    """
    quelle = js()
    assert "punkt.fremd = fremd" in quelle
    assert 'p.fremd ? "FREMD: " + p.fremd : ""' in quelle
    # Die Prüfung muss **vor** dem Start-Zweig stehen, sonst gilt sie wieder
    # nur für die eine Zeile.
    i = quelle.index("const fremd = fremdeSpuren(3);")
    j = quelle.index('if (grund === "start") {', i - 1200)
    assert i < j, "steckt wieder nur im Start-Zweig"


def test_melden_stoert_nie():
    """Eine kaputte Erweiterung darf die App nicht mitreißen – erst recht
    nicht die Stelle, die sie melden soll."""
    koerper = block("fremdeSpuren")
    assert "try {" in koerper and "catch" in koerper


def test_es_wird_nur_gemeldet_nie_geblockt():
    """Es ist Svens Browser. Eine Passwort-Ausfüllhilfe hat dort gute
    Gründe zu sein – die App entfernt nichts."""
    koerper = block("fremdeSpuren")
    for verboten in (".remove()", "removeChild", "innerHTML ="):
        assert verboten not in koerper, f"{verboten} greift ein statt zu melden"
