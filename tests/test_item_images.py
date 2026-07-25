"""Katalogbilder werden entdoppelt: dieselbe Figur nur einmal, egal über
welchen BrickLink-Endpunkt/welche Auflösung."""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "img.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " created_at) VALUES ('a', 'x', 1, ?)", (now,))
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "a", True)
    return c


def test_img_key_collapses_bricklink_endpoints():
    # Verschiedene Endpunkte/Auflösungen derselben Nummer → gleicher Schlüssel
    a = main._img_key("//img.bricklink.com/ItemImage/MN/0/sw0001.png")
    b = main._img_key("https://img.bricklink.com/ML/sw0001.jpg")
    c = main._img_key("https://img.bricklink.com/ItemImage/MN/0/sw0001.t1.png")
    assert a == b == c == "bl:sw0001"
    # Andere Quelle bleibt eigenständig
    assert main._img_key("https://cdn.rebrickable.com/x/sw0001.jpg") != a


def test_same_figure_collapses_to_one_prefers_api(client, monkeypatch):
    # API liefert das ML-Bild (andere Auflösung) – dasselbe Motiv wie das
    # konstruierte ItemImage → nur eins, und zwar das API-Bild.
    monkeypatch.setattr(
        integrations, "bricklink_item",
        lambda t, n: {"img_url": "https://img.bricklink.com/ML/sw0001.jpg"})
    imgs = client.get("/api/images/minifig/sw0001").json()["images"]
    assert imgs == ["https://img.bricklink.com/ML/sw0001.jpg"]


def test_falls_back_to_itemimage_without_api(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: False)
    imgs = client.get("/api/images/minifig/sw0001").json()["images"]
    assert imgs == ["https://img.bricklink.com/ItemImage/MN/0/sw0001.png"]


def test_manual_number_has_no_catalog_images(client):
    assert client.get("/api/images/minifig/manuell-5").json()["images"] == []
