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


def test_nur_das_verlustfreie_bild_statt_zweier_fassungen(client, monkeypatch):
    """Die API liefert `/ML/*.jpg`, die gebaute Adresse `ItemImage/*.png`.

    An vier Figuren nachgemessen (29.08.2026): **dieselben Maße**, aber
    44–82 KB JPEG gegen 85–129 KB verlustfreies PNG. Zwei Fassungen
    desselben Motivs in der Galerie sind kein Gewinn, sondern ein Abruf und
    ein Wisch zu viel – und der API-Aufruf kostete Tageskontingent.

    Der alte Test hieß `…prefers_api` und stützte sich auf den Kommentar
    „meist bessere Auflösung". Gemessen war das nie.
    """
    gefragt = []
    monkeypatch.setattr(
        integrations, "bricklink_item",
        lambda t, n: gefragt.append(n) or {
            "img_url": "https://img.bricklink.com/ML/sw0001.jpg"})
    imgs = client.get("/api/images/minifig/sw0001").json()["images"]
    assert imgs == ["https://img.bricklink.com/ItemImage/MN/0/sw0001.png"]
    assert gefragt == [], "die API wird dafür gar nicht mehr gefragt"


def test_falls_back_to_itemimage_without_api(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: False)
    imgs = client.get("/api/images/minifig/sw0001").json()["images"]
    assert imgs == ["https://img.bricklink.com/ItemImage/MN/0/sw0001.png"]


def test_manual_number_has_no_catalog_images(client):
    assert client.get("/api/images/minifig/manuell-5").json()["images"] == []
