"""Eigene Bilder gehören in die manuelle Sicherung.

Sie sind Dateien, keine Datenbankzeilen. Ohne sie trüge die Sicherung nur
den Verweis, und nach einem Umzug zeigten die Artikel ins Leere. Mitgenommen
werden sie als Base64 im selben Dokument – eine Datei bleibt eine Datei, und
beide Einspiel-Wege (Admin und Ersteinrichtung) müssen nichts Neues können.
"""
import base64
import io
import time

import pytest
from PIL import Image

import core
import main
from fastapi.testclient import TestClient


def _bild(farbe=(200, 30, 30)) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", (900, 700), farbe).save(puffer, format="JPEG")
    return puffer.getvalue()


def _admin(c):
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return uid


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "a" / "brickfolio.db"))
    (tmp_path / "a").mkdir()
    core.init_db()
    c = TestClient(main.app)
    _admin(c)
    return c


def _mit_bild(client, farbe=(200, 30, 30)):
    """Ein eigenes Bild hochladen und an einen Sammlungseintrag hängen."""
    url = client.post("/api/upload_image",
                      files={"file": ("s.jpg", _bild(farbe), "image/jpeg")}
                      ).json()["url"]
    client.post("/api/collection", json={
        "item_id": "sw0978", "item_type": "minifig", "name": "Luke",
        "img_url": url, "condition": "used"})
    return url


def test_ohne_nachfrage_bleiben_bilder_draussen(client):
    """Die alte Sicherung soll nicht plötzlich zehnmal so groß werden."""
    _mit_bild(client)
    dump = client.get("/api/backup").json()
    assert "uploads" not in dump


def test_mit_bildern_sind_sie_drin(client):
    url = _mit_bild(client)
    dump = client.get("/api/backup?images=1").json()
    name = url.rsplit("/", 1)[-1]
    assert name in dump["uploads"]
    assert base64.b64decode(dump["uploads"][name])[:2] == b"\xff\xd8"  # JPEG


def test_uploads_info_zaehlt(client):
    _mit_bild(client)
    _mit_bild(client, (30, 30, 200))
    info = client.get("/api/uploads_info").json()
    assert info["count"] == 2
    assert info["bytes"] > 0
    assert info["max_bytes"] > info["bytes"]


def test_umzug_auf_eine_leere_instanz(tmp_path, monkeypatch):
    """Der eigentliche Zweck: Nach dem Einspielen ist das Bild wieder da –
    unter demselben Namen, sonst passte der Verweis nicht mehr."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "alt" / "brickfolio.db"))
    (tmp_path / "alt").mkdir()
    core.init_db()
    alt = TestClient(main.app)
    _admin(alt)
    url = _mit_bild(alt)
    dump = alt.get("/api/backup?images=1").json()
    original = alt.get(url).content

    # Zweite, frische Instanz – eigenes Verzeichnis, nichts darin.
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "neu" / "brickfolio.db"))
    (tmp_path / "neu").mkdir()
    core.init_db()
    neu = TestClient(main.app)
    assert neu.get(url).status_code == 404          # vorher: nichts da
    r = neu.post("/api/setup/restore", json=dump)
    assert r.status_code == 200
    assert r.json()["restored"]["uploads"] == 1

    neu.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    assert neu.get("/api/collection").json()["items"][0]["img_url"] == url
    assert neu.get(url).content == original         # Datei identisch


def test_alte_sicherung_ohne_bilder_geht_weiter(client):
    """Wer eine Sicherung von gestern einspielt, darf nicht auflaufen."""
    _mit_bild(client)
    dump = client.get("/api/backup").json()
    r = client.post("/api/restore", json=dump)
    assert r.status_code == 200
    assert r.json()["restored"]["uploads"] == 0


def test_fremde_dateinamen_werden_nicht_geschrieben(client):
    """Der Name aus der Sicherung wird zum Dateinamen – eine manipulierte
    Datei darf damit nicht aus dem Ordner ausbrechen."""
    dump = client.get("/api/backup").json()
    dump["uploads"] = {
        "../../boese.jpg": base64.b64encode(b"x").decode(),
        "/etc/passwd": base64.b64encode(b"x").decode(),
        "nicht-hex.jpg": base64.b64encode(b"x").decode(),
        "a" * 32 + ".png": base64.b64encode(b"x").decode(),
    }
    r = client.post("/api/restore", json=dump)
    assert r.status_code == 200
    assert r.json()["restored"]["uploads"] == 0


def test_kaputte_base64_kippt_nicht_die_sicherung(client):
    dump = client.get("/api/backup").json()
    dump["uploads"] = {"b" * 32 + ".jpg": "kein gültiges base64 !!!"}
    r = client.post("/api/restore", json=dump)
    assert r.status_code == 200
    assert r.json()["restored"]["uploads"] == 0


def test_zu_grosse_sammlung_wird_abgelehnt(client, monkeypatch):
    """Statt eine unbrauchbar große Datei zu bauen, sagt die App es."""
    _mit_bild(client)
    monkeypatch.setattr(main, "UPLOADS_MAX", 10)
    r = client.get("/api/backup?images=1")
    assert r.status_code == 413
    assert "data/uploads/" in r.json()["detail"]
