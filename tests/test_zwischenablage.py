"""Kopieren muss auch dann gehen, wenn der Browser sich sperrt.

Zwei Dinge stehen hier auf dem Spiel:

* **Die Reihenfolge.** `navigator.clipboard.writeText()` ist ein Versprechen.
  Wer darauf wartet, gibt die Benutzergeste des Klicks aus der Hand – und
  genau die verlangt der Rückfallweg `execCommand`. Stand die moderne
  Schnittstelle vorn und schlug fehl, kam der Rückfall zu spät; er half also
  nur, wenn er nicht gebraucht wurde. Der synchrone Weg muss zuerst laufen.
* **Der Ausweg.** Klappt beides nicht, darf der Text nicht einfach weg sein –
  er wird zum Markieren hingelegt, und der Grund wird genannt.
"""

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "frontend" / "app.js"


def js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def helfer() -> str:
    quelle = js()
    anfang = quelle.index("async function inZwischenablage(")
    return quelle[anfang:quelle.index("\n}", anfang)]


def test_helfer_vorhanden():
    assert "async function inZwischenablage(" in js()


def test_synchroner_weg_kommt_zuerst():
    """Der eigentliche Kern – und der Grund, warum es vorher scheitern konnte."""
    k = helfer()
    zuerst = k.index('document.execCommand("copy")')
    danach = k.index("navigator.clipboard.writeText(")
    assert zuerst < danach, ("execCommand muss vor dem Versprechen laufen, "
                             "sonst ist die Benutzergeste aufgebraucht")


def test_kein_await_vor_dem_execcommand():
    """Auch ein anderes `await` davor würde die Geste kosten."""
    k = helfer()
    davor = k[:k.index('document.execCommand("copy")')]
    assert "await" not in davor


def test_grund_wird_festgehalten():
    """„Geht nicht" ohne Grund ist als Auskunft wertlos."""
    k = helfer()
    assert "kopierGrund =" in k
    assert "gruende.push" in k
    assert "spur(" in k


def test_nur_ein_direkter_zugriff_auf_die_zwischenablage():
    treffer = re.findall(r"navigator\.clipboard\.writeText\(", js())
    assert len(treffer) == 1, (
        f"{len(treffer)} Aufrufe – erlaubt ist nur der im Helfer"
    )


def test_alle_kopier_knoepfe_gehen_denselben_weg():
    quelle = js()
    for knopf in ("btn-tfa-copy", "cf-copy", "btn-errors-copy", "btn-diag-copy"):
        anfang = quelle.index(knopf)
        assert "kopieren(" in quelle[anfang:anfang + 3000], (
            f"{knopf} kopiert nicht über den gemeinsamen Weg"
        )


def test_bei_fehlschlag_wird_der_text_hingelegt():
    quelle = js()
    anfang = quelle.index("async function kopieren(")
    koerper = quelle[anfang:anfang + 500]
    assert "textZumMarkieren(" in koerper
    assert "kopierGrundText()" in koerper


def test_der_ausweg_setzt_den_text_nicht_ins_html():
    """Ein Fehlerbericht kann alles Mögliche enthalten – als Text, nicht als
    Auszeichnung."""
    quelle = js()
    anfang = quelle.index("function textZumMarkieren(")
    koerper = quelle[anfang:quelle.index("\n}", anfang)]
    assert "feld.value = text" in koerper
    assert "innerHTML" not in koerper.split("feld.value")[1]
