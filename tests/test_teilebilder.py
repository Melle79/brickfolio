"""Teile brauchen eine andere Bildadresse als Figuren und Sets.

`ItemImage/<code>/0/<nr>.png` trägt bei Figuren und Sets, weil die keine
Farbe haben. Ein Teil schon – dort steht statt der Null die Farbnummer, und
die kennt der Server hier nicht. Am 29.08.2026 an sieben Teilen geprüft:
`ItemImage/PN/0/…` war **jedes Mal** ein 404.

Weil das die einzige Adresse in der Galerie war, ging die Großansicht
sofort wieder zu – „öffnet kurz und schließt sich wieder".
"""
import re
from pathlib import Path

import main

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def test_teile_bekommen_die_farbunabhaengige_adresse():
    quelle = (Path(__file__).resolve().parents[1]
              / "backend" / "main.py").read_text()
    m = re.search(r"def item_images\(.*?\n    return \{\"images\"", quelle, re.S)
    assert m, "item_images nicht gefunden"
    f = m.group(0)
    assert 'if art == "part":' in f
    assert 'img.bricklink.com/PL/{safe}.jpg' in f
    # Und die alte Form darf für Teile nicht mehr greifen.
    assert f.index('if art == "part":') < f.index("ItemImage/{code}/0/")


def test_figuren_und_sets_bleiben_bei_itemimage():
    """Dort ist die Null richtig – und `/ML/` fehlte bei 102 Figuren."""
    quelle = (Path(__file__).resolve().parents[1]
              / "backend" / "main.py").read_text()
    assert '_BL_IMG_CODE = {"minifig": "MN", "part": "PN", "set": "SN"}' in quelle
    assert "ItemImage/{code}/0/{safe}.png" in quelle


def test_die_galerie_faellt_auf_das_kartenbild_zurueck():
    """Trägt das Katalogbild nicht, ist die Adresse von der Karte das
    Einzige, was bleibt – zuklappen ist die schlechteste Antwort."""
    js = APP_JS.read_text()
    m = re.search(r'\$\("lightbox-img"\)\.addEventListener\("error".*?\n  \}\);',
                  js, re.S)
    assert m, "Der Fehlerbehandler wurde nicht gefunden"
    f = m.group(0)
    assert "gallery.ersatz" in f
    # Der Rückfall muss **vor** dem Zuklappen kommen.
    assert f.index("gallery.ersatz") < f.index("closeGallery()")
    # Und wenn auch der nicht trägt, nicht wortlos verschwinden.
    assert "toast(" in f


def test_der_rueckfall_wird_beim_oeffnen_gemerkt():
    js = APP_JS.read_text()
    m = re.search(r"function openGallery\(startUrl, gid, gtype\) \{.*?\n\}\n",
                  js, re.S)
    assert m
    assert "ersatz: startUrl" in m.group(0)
