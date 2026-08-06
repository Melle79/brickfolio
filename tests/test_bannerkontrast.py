"""Das Update-Banner muss man lesen können – in jedem Design.

Aus dem Betrieb, per Bildschirmfoto: „⬆️ Update v2.21.0 verfügbar!" stand in
fast weißer Schrift auf hellblauem Grund, der Verweis daneben in der
Browser-Vorgabe für besuchte Links. Gemessen waren das **1,66 : 1** für den
Text und **1,25 : 1** für den Verweis – lesbar wären 4,5 : 1.

Die Ursache steckt in der Design-Umschaltung: Die Fläche des Banners ist
`--yellow`, und das ist in Galaxie ein helles Gelb, in Nova sogar ein helles
Blau. Die Schriftfarbe blieb dabei die des dunklen Designs, also hell. Genau
die Meldung, die auffallen soll, war damit unsichtbar.
"""
import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
MINDESTENS = 4.5          # WCAG AA für normalen Text


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def hex_zu_rgb(wert: str) -> tuple:
    w = wert.strip().lstrip("#")
    if len(w) == 3:
        w = "".join(c * 2 for c in w)
    return tuple(int(w[i:i + 2], 16) for i in (0, 2, 4))


def helligkeit(rgb: tuple) -> float:
    teile = []
    for k in rgb:
        v = k / 255
        teile.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * teile[0] + 0.7152 * teile[1] + 0.0722 * teile[2]


def kontrast(a: str, b: str) -> float:
    l1, l2 = helligkeit(hex_zu_rgb(a)), helligkeit(hex_zu_rgb(b))
    hell, dunkel = max(l1, l2), min(l1, l2)
    return (hell + 0.05) / (dunkel + 0.05)


def variable(name: str, design: str) -> str:
    """Wert einer CSS-Variablen im jeweiligen Design.

    Die Design-Wähler kommen dutzendfach vor; gesucht ist der eine Block, in
    dem die Variablen stehen. Deshalb wird der Block über die Variable selbst
    gefunden und nicht über die erste Fundstelle des Wählers.
    """
    c = css()
    wähler = ":root" if design == "classic" else f'[data-theme="{design}"]'
    treffer = re.search(
        rf"{re.escape(wähler)}[^{{]*\{{[^}}]*?{re.escape(name)}:\s*"
        rf"(#[0-9A-Fa-f]{{3,8}})", c, re.S)
    assert treffer, f"{name} nicht gefunden für {design}"
    return treffer.group(1)


def banner_schriftfarbe(design: str) -> str:
    """Welche Farbe trägt der Bannertext? Ohne eigene Regel erbt er die
    Textfarbe der Seite – und die ist im dunklen Design hell."""
    c = css()
    if design != "classic":
        muster = rf'\[data-theme="{design}"\][^{{]*\.update-banner[^{{]*\{{([^}}]*)\}}'
        for block in re.findall(muster, c):
            farbe = re.search(r"color:\s*(#[0-9A-Fa-f]{3,8})", block)
            if farbe:
                return farbe.group(1)
    return variable("--ink", design)


@pytest.mark.parametrize("design", ["classic", "galaxy", "nova"])
def test_der_bannertext_ist_lesbar(design):
    grund = variable("--yellow", design)
    schrift = banner_schriftfarbe(design)
    wert = kontrast(grund, schrift)
    assert wert >= MINDESTENS, (
        f"{design}: Text {schrift} auf {grund} ergibt nur {wert:.2f} : 1")


def test_der_verweis_erbt_die_schriftfarbe():
    """Ohne eigene Farbe nahm er die Browser-Vorgabe – und die kennt den
    Untergrund nicht. Einmal besucht war er vollends weg."""
    block = re.search(r"\.update-banner a\s*\{([^}]*)\}", css())
    assert block, ".update-banner a fehlt"
    assert "color: inherit" in block.group(1), (
        "der Verweis nimmt weiter die Browser-Vorgabe")


def test_der_verweis_bleibt_als_verweis_erkennbar():
    """Wenn die Farbe ihn nicht mehr abhebt, muss es die Unterstreichung tun."""
    block = re.search(r"\.update-banner a\s*\{([^}]*)\}", css())
    assert "text-decoration: underline" in block.group(1), (
        "ohne Farbe *und* ohne Unterstreichung ist er kein Verweis mehr")


def test_beide_dunklen_designs_setzen_die_farbe_wirklich():
    """Der Test oben würde auch grün, wenn --ink zufällig dunkel wäre.
    Hier steht, dass die Regel tatsächlich existiert."""
    c = css()
    for design in ("galaxy", "nova"):
        assert re.search(rf'\[data-theme="{design}"\] \.update-banner', c), (
            f"{design} setzt keine eigene Schriftfarbe fürs Banner")
