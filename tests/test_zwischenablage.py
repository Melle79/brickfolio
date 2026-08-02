"""Kopieren muss auch ohne sicheren Kontext gehen.

Über die IP-Adresse im Heimnetz (http://192.168.…) gibt der Browser
`navigator.clipboard` gar nicht erst heraus. Dafür gibt es den Helfer
`inZwischenablage()` mit dem Rückfallweg über ein unsichtbares Textfeld –
und alle Kopier-Knöpfe müssen ihn benutzen, sonst bleibt genau einer
übrig, der im Heimnetz scheitert.
"""

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "frontend" / "app.js"


def js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_helfer_vorhanden():
    assert "async function inZwischenablage(" in js()


def test_helfer_prueft_sicheren_kontext():
    """Ohne sicheren Kontext darf der Helfer nicht in den Fehler laufen,
    sondern muss direkt auf den Rückfallweg gehen."""
    quelle = js()
    anfang = quelle.index("async function inZwischenablage(")
    koerper = quelle[anfang:anfang + 1600]
    assert "window.isSecureContext" in koerper
    assert "document.execCommand(\"copy\")" in koerper


def test_nur_der_helfer_spricht_die_zwischenablage_an():
    """Jeder direkte Aufruf wäre ein Knopf, der im Heimnetz nicht kopiert."""
    treffer = re.findall(r"navigator\.clipboard\.writeText", js())
    assert len(treffer) == 1, (
        f"{len(treffer)} direkte Aufrufe – erlaubt ist nur der im Helfer"
    )


def test_alle_kopier_knoepfe_nutzen_den_helfer():
    quelle = js()
    for knopf in ("btn-tfa-copy", "cf-copy", "btn-errors-copy", "btn-diag-copy"):
        anfang = quelle.index(knopf)
        assert "inZwischenablage(" in quelle[anfang:anfang + 3000], (
            f"{knopf} kopiert nicht über den Helfer"
        )
