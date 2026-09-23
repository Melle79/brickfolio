"""Zu klein abgelegte Katalogbilder holen sich selbst nach.

Bis 2.87.1 wurde mit 400 Pixeln abgelegt – das reichte, solange das Popup
eine Briefmarke von 72 Pixeln zeigte. Seit es mit dem Bild über die volle
Breite aufmacht, sind 400 zu wenig; schon abgelegte Bilder blieben aber
klein.

Ein Sammellauf über alle Bilder käme nicht in Frage: Er ginge gegen
dasselbe Tageskontingent bei BrickLink wie die Preise, und zwar für Bilder,
die vielleicht nie jemand ansieht. Nachgeholt wird deshalb genau dann, wenn
jemand die Figur oder das Set **aufruft** – also beim vollen Bild, nicht
beim Daumennagel im Raster. Wer durch 800 Karten blättert, löst nichts aus.
"""
import io
import time
from pathlib import Path

import pytest
from PIL import Image

import core
import main
from fastapi.testclient import TestClient

ADRESSE = "https://img.bricklink.com/ItemImage/MN/0/sw0402.png"


def _bild(kante: int) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", (kante, kante), (120, 60, 60)).save(puffer, "JPEG")
    return puffer.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "d.db"))
    core.init_db()
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 0, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


@pytest.fixture
def altes_bild(client):
    """Ein Bild, wie es vor 2.88.0 abgelegt wurde: 400 Pixel."""
    pfad = Path(main._katalog_dir()) / main._katalog_name(ADRESSE)
    pfad.write_bytes(_bild(400))
    return pfad


def test_das_volle_bild_stoesst_das_nachholen_an(client, altes_bild, monkeypatch):
    geholt = []

    def falscher_abruf(url, hosts):
        geholt.append(url)
        return _bild(800)

    monkeypatch.setattr(main.integrations, "fetch_catalog_image", falscher_abruf)
    r = client.get("/catalog", params={"u": ADRESSE})
    assert r.status_code == 200
    # Der Abruf läuft im Hintergrund – der Aufrufer bekommt diesmal noch das
    # alte Bild, damit sich das Fenster nicht aufhält.
    for _ in range(50):
        if geholt:
            break
        time.sleep(0.05)
    assert geholt == [ADRESSE]
    for _ in range(50):
        with Image.open(altes_bild) as b:
            if max(b.size) == 800:
                break
        time.sleep(0.05)
    with Image.open(altes_bild) as b:
        assert max(b.size) == 800


def test_der_daumennagel_stoesst_nichts_an(client, altes_bild, monkeypatch):
    """Sonst löste ein Blick auf die Sammlung 800 Abrufe aus."""
    geholt = []
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: geholt.append(url) or _bild(800))
    r = client.get("/catalog", params={"u": ADRESSE, "s": 160})
    assert r.status_code == 200
    time.sleep(0.4)
    assert geholt == []


def test_ein_grosses_bild_wird_nicht_noch_einmal_geholt(client, monkeypatch):
    """Sonst holte jedes Öffnen dasselbe Bild erneut – jedes Mal gegen das
    Tageskontingent."""
    pfad = Path(main._katalog_dir()) / main._katalog_name(ADRESSE)
    pfad.write_bytes(_bild(main.BILD_KANTE))
    geholt = []
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: geholt.append(url) or _bild(800))
    assert client.get("/catalog", params={"u": ADRESSE}).status_code == 200
    time.sleep(0.4)
    assert geholt == []


def test_die_alten_daumennaegel_verschwinden(client, altes_bild, monkeypatch):
    """Sie stammen vom kleinen Bild – blieben sie liegen, sähe die Sammlung
    weiter ausgefranst aus."""
    daumen = Path(str(altes_bild) + ".160.jpg")
    daumen.write_bytes(_bild(160))
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: _bild(800))
    client.get("/catalog", params={"u": ADRESSE})
    for _ in range(50):
        if not daumen.exists():
            break
        time.sleep(0.05)
    assert not daumen.exists()
