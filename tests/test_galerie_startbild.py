"""Die Galerie darf dieselbe Figur nicht zweimal zeigen.

Beim Scannen speichert die App die Adresse, die der Erkenner liefert – bei
Brickognize ein kleines Vorschaubild von einer ganz anderen Adresse. Über
den Schlüssel fiel es nicht mit dem BrickLink-Katalogbild zusammen, und die
Galerie zeigte „1/2" mit demselben Motiv, das zweite Bild besser als das
erste. Gemessen an Svens Sammlung am 29.08.2026: 379 von 910 Einträgen
betroffen, 368 davon Vorschaubilder von Brickognize.
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def _open_gallery() -> str:
    js = APP_JS.read_text()
    m = re.search(r"function openGallery\(startUrl, gid, gtype\) \{.*?\n\}\n",
                  js, re.S)
    assert m, "openGallery nicht gefunden"
    return m.group(0)


def test_startbild_faellt_weg_wenn_der_server_liefert():
    f = _open_gallery()
    assert "if (startUrl && !urls.length) urls.push(startUrl);" in f, \
        "Das Startbild darf nur noch als letzte Rettung dazukommen"


def test_das_startbild_wird_nicht_mehr_ueber_den_schluessel_geprueft():
    """Der alte Weg verglich Schlüssel – und zwei verschiedene Quellen
    haben nun einmal verschiedene Schlüssel, auch wenn dieselbe Figur
    darauf ist."""
    f = _open_gallery()
    assert "seen.has(imgKey(startUrl))" not in f
    assert "urls.unshift(startUrl)" not in f


def test_leere_serverliste_laesst_das_startbild_stehen():
    """Eigene Figuren haben kein Katalogbild – dann ist das Startbild
    alles, was es gibt."""
    f = _open_gallery()
    # Erst füllen, dann als letzte Rettung anhängen: Die Reihenfolge im
    # Code ist der ganze Beweis.
    assert f.index("(d.images || []).forEach") < f.index("!urls.length")
