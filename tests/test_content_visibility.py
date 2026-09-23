"""`content-visibility: auto` steht wieder auf den Sammlungskarten.

Es war am 29.08.2026 versuchsweise ausgebaut: Von 40 Absturz-Dumps auf
Svens Rechner sind alle 40 auf Brickfolio, und `content-visibility` ist
das Ungewöhnlichste, was diese Seite tut.

**Der Versuch ist gelaufen, das Ergebnis war negativ.** Der Bericht zu
2.70.0 führt drei weitere Abstürze, alle nach dem Ausbau. Die Zeile spart
dem Browser echte Arbeit (gemessen: statt 815 Hintergrundbildern beim
Öffnen nur noch 16) und steht deshalb wieder da.

Dieser Test hält beides fest: dass sie da ist, und warum sie nicht noch
einmal als Verdächtige herhalten muss.
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "style.css"


def _regeln(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_content_visibility_steht_auf_den_sammlungskarten():
    regeln = _regeln(CSS.read_text())
    assert "content-visibility: auto" in regeln
    block = re.search(r"#collection-list \.card \{([^}]*)\}", regeln)
    assert block, "Regel für die Sammlungskarten nicht gefunden"
    assert "content-visibility: auto" in block.group(1)


def test_die_hoehenangabe_gehoert_dazu():
    """Ohne `contain-intrinsic-size` springt die Bildlaufleiste beim
    Scrollen, weil der Browser die Höhe nicht kennt."""
    regeln = _regeln(CSS.read_text())
    for hoehe in ("104px", "236px", "132px"):       # Liste, Raster, kompakt
        assert "auto %s" % hoehe in regeln, hoehe


def test_die_ersatzgroesse_gilt_nur_fuer_die_hoehe():
    """**Ein einzelner Wert gilt für beide Achsen** – das ist die Falle.

    `contain-intrinsic-size: auto 236px` liest sich wie „236 Pixel hoch",
    setzt aber auch die Breite. Karten außerhalb des Sichtfelds meldeten
    damit 236 px Breite; weil Rasterfelder `min-width: auto` haben, konnte
    `1fr` nicht darunter, und die zwei Spalten rechneten 260 px statt 197.
    Die Sammlung stand 126 px über den Rand und ließ sich seitlich
    schieben (23.09.2026).

    Sichtbar war das nur bei vielen Einträgen: Wo nichts übersprungen wird,
    gibt es keine Ersatzgröße. Mit sieben Karten in der Probe war nie etwas
    zu sehen, mit 780 sofort."""
    regeln = _regeln(CSS.read_text())
    einzeln = re.findall(r"contain-intrinsic-size:\s*auto\s+\d+px", regeln)
    assert not einzeln, (
        "Einzelwert gilt für beide Achsen und bläht die Spalten: %s" % einzeln)
    # Nur dort, wo überhaupt eine Länge steht: Der Abschalt-Schalter für die
    # Fehlersuche setzt `auto !important` ganz ohne Maß – der hebt die
    # Ersatzgröße auf, statt eine zu setzen.
    for regel in re.findall(r"contain-intrinsic-size:([^;]*);", regeln):
        if re.search(r"\d+px", regel):
            assert "none" in regel, regel.strip()


def test_eine_karte_darf_ihre_spalte_nicht_aufblaehen():
    """Gürtel und Hosenträger: Kennt ein Browser die Zwei-Wert-Schreibweise
    nicht, darf `min-width: auto` nicht wieder zum Einfallstor werden."""
    regeln = _regeln(CSS.read_text())
    m = re.search(r"\.results\.grid-mode > \.card,[^{]*\{([^}]*)\}", regeln)
    assert m, "Regel für schrumpfbare Rasterfelder fehlt"
    assert "min-width: 0" in m.group(1)


def test_das_ergebnis_des_versuchs_steht_dabei():
    """Damit niemand – ich eingeschlossen – denselben Versuch noch einmal
    macht."""
    text = CSS.read_text()
    assert "wieder eingebaut" in text
    assert "2.70.0" in text and "drei" in text
