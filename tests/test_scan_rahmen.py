"""Der Rahmen aus der Erkennung muss zum Bild des Browsers passen.

Brickognize rahmt sauber ein – geprüft am 20.09.2026 mit einem eigenen Foto,
der zurückgegebene Rahmen lag genau auf der Figur. Nur gilt er für das Bild,
auf dem der **Dienst** gearbeitet hat, und das ist nicht das geschickte: Er
rechnet selbst auf höchstens 1024 Pixel herunter. Aus 900×1200 wird dort
768×1024, und ein Rahmen daraus sitzt im Browser um 1024/1200 = 0,853 zu
klein und zu weit links oben.

Sichtbar wurde es erst bei mehreren Figuren nebeneinander: Bei einer
einzelnen sieht ein etwas zu kleiner Rahmen richtig aus.

**Zwei falsche Fährten auf dem Weg dahin**, beide hier festgehalten, damit
sie niemand noch einmal verfolgt:

1. Eine erste Probe mit demselben Motiv in zwei Größen (600×800, 450×600)
   zeigte den Dienst die geschickten Maße *echoen* – beide lagen aber unter
   1024, wo er nichts verkleinert.
2. Daraufhin galt der Browser als Verursacher (er habe größer als 1200
   geschickt). Das Protokoll des Servers zeigte dann `Upload 900x1200,
   Dienst 768x1024`: Der Browser war es nie.

Die Umrechnung nimmt deshalb `image_width`/`image_height` aus der Antwort –
die Zahlen gelten, ganz gleich wer verkleinert hat.
"""
import io

import pytest
from PIL import Image

import integrations


def _bild(breite, hoehe, drehung=None):
    im = Image.new("RGB", (breite, hoehe), (200, 200, 200))
    p = io.BytesIO()
    if drehung:
        exif = im.getexif()
        exif[274] = drehung
        im.save(p, format="JPEG", exif=exif)
    else:
        im.save(p, format="JPEG")
    return p.getvalue()


class _Antwort:
    status_code = 200

    def __init__(self, box):
        self._box = box

    def raise_for_status(self):
        pass

    def json(self):
        return {"items": [{"id": "sw0973", "name": "Lando", "type": "fig",
                           "score": 0.9, "img_url": ""}],
                "listing_id": "x", "bounding_box": self._box}


@pytest.fixture
def dienst(monkeypatch):
    """Der Dienst antwortet immer mit demselben Rahmen im 1200er Maßstab."""
    gesehen = {}

    def post(url, files=None, **rest):
        roh = files["query_image"][1]
        with Image.open(io.BytesIO(roh)) as im:
            gesehen["masse"] = im.size
        return _Antwort({"left": 150.0, "upper": 300.0,
                         "right": 450.0, "lower": 900.0,
                         "image_width": float(gesehen["masse"][0]),
                         "image_height": float(gesehen["masse"][1]),
                         "score": 0.8})

    monkeypatch.setattr(integrations.requests, "post", post)
    return gesehen


def test_grosses_bild_wird_zurueckgerechnet(dienst):
    """Der Dienst arbeitet kleiner, als hochgeladen wurde – der Rahmen wächst
    auf die Maße des Uploads zurück."""
    d = integrations.recognize(_bild(1050, 1400))
    assert dienst["masse"] == (900, 1200), "der Dienst sieht das verkleinerte Bild"
    r = d["box"]
    assert r["left"] == pytest.approx(150 * 1050 / 900, abs=0.5)
    assert r["upper"] == pytest.approx(300 * 1400 / 1200, abs=0.5)
    assert r["right"] == pytest.approx(450 * 1050 / 900, abs=0.5)
    assert r["lower"] == pytest.approx(900 * 1400 / 1200, abs=0.5)


def test_kleines_bild_bleibt_unveraendert(dienst):
    """Der Normalfall: Der Browser schickt schon 1200 – nichts zu rechnen."""
    d = integrations.recognize(_bild(900, 1200))
    assert dienst["masse"] == (900, 1200)
    r = d["box"]
    assert (r["left"], r["upper"], r["right"], r["lower"]) == (150, 300, 450, 900)


def test_gedrehtes_bild_zaehlt_wie_der_browser_es_sieht(dienst):
    """EXIF-Drehung: Der Browser zeigt hochkant, die Datei liegt quer.

    `prepare_image` dreht mit, also muss auch die Umrechnung die gedrehten
    Maße nehmen – sonst wären Breite und Höhe vertauscht.
    """
    d = integrations.recognize(_bild(1400, 1050, drehung=6))
    assert dienst["masse"] == (900, 1200), "gedreht und verkleinert"
    r = d["box"]
    assert r["left"] == pytest.approx(150 * 1050 / 900, abs=0.5)
    assert r["lower"] == pytest.approx(900 * 1400 / 1200, abs=0.5)


def test_ohne_masse_vom_dienst_bleibt_alles_wie_es_war(monkeypatch):
    """Ältere Antworten ohne `image_width` dürfen nichts kaputt machen."""
    def post(url, files=None, **rest):
        return _Antwort({"left": 10.0, "upper": 20.0, "right": 30.0,
                         "lower": 40.0, "score": 0.5})
    monkeypatch.setattr(integrations.requests, "post", post)
    r = integrations.recognize(_bild(2000, 2000))["box"]
    assert (r["left"], r["upper"], r["right"], r["lower"]) == (10, 20, 30, 40)


def test_dienst_rechnet_selbst_kleiner(monkeypatch):
    """**Der eigentliche Fall, gemessen am 20.09.2026.**

    Der Browser schickt 900×1200 – richtig verkleinert. Brickognize rechnet
    intern auf 768×1024 herunter und antwortet in diesen Maßen. Ohne
    Umrechnung säße jeder Rahmen um 0,853 zu klein.
    """
    def post(url, files=None, **rest):
        return _Antwort({"left": 128.0, "upper": 256.0, "right": 384.0,
                         "lower": 768.0, "image_width": 768.0,
                         "image_height": 1024.0, "score": 0.9})
    monkeypatch.setattr(integrations.requests, "post", post)
    r = integrations.recognize(_bild(900, 1200))["box"]
    assert r["left"] == pytest.approx(128 * 900 / 768, abs=0.5)
    assert r["upper"] == pytest.approx(256 * 1200 / 1024, abs=0.5)
    assert r["right"] == pytest.approx(384 * 900 / 768, abs=0.5)
    assert r["lower"] == pytest.approx(768 * 1200 / 1024, abs=0.5)
