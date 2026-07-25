"""Katalogbilder werden entdoppelt: gleiche Bilder nur einmal."""
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


def test_same_image_collapses_to_one(client, monkeypatch):
    # API liefert dasselbe Bild wie das konstruierte ItemImage – nur „//".
    monkeypatch.setattr(
        integrations, "bricklink_item",
        lambda t, n: {"img_url": "//img.bricklink.com/ItemImage/MN/0/sw0001.png"})
    imgs = client.get("/api/images/minifig/sw0001").json()["images"]
    assert imgs == ["https://img.bricklink.com/ItemImage/MN/0/sw0001.png"]


def test_genuinely_different_images_are_kept(client, monkeypatch):
    monkeypatch.setattr(
        integrations, "bricklink_item",
        lambda t, n: {"img_url": "https://example.com/anders.png"})
    imgs = client.get("/api/images/minifig/sw0001").json()["images"]
    assert len(imgs) == 2 and "example.com/anders.png" in imgs[1]


def test_manual_number_has_no_catalog_images(client):
    assert client.get("/api/images/minifig/manuell-5").json()["images"] == []
