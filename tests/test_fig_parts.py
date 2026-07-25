"""Tests für /api/fig_parts: aus welchen Teilen besteht eine Minifigur."""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "fp.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('finn', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "finn", True)
    return c


def _parts(no):
    return [
        {"item_id": "973pb0001", "item_type": "part", "name": "Torso",
         "color_id": 11, "color_name": "Black", "qty": 1,
         "img_url": "https://img.bricklink.com/ItemImage/PN/11/973pb0001.png",
         "bricklink_url": ""},
        {"item_id": "3626cpb", "item_type": "part", "name": "Head",
         "color_id": 5, "color_name": "Tan", "qty": 1,
         "img_url": "https://img.bricklink.com/ItemImage/PN/5/3626cpb.png",
         "bricklink_url": ""},
    ]


def test_returns_parts(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "bricklink_minifig_parts", _parts)
    items = client.get("/api/fig_parts/sw1213").json()["items"]
    assert [p["item_id"] for p in items] == ["973pb0001", "3626cpb"]
    assert items[0]["color_name"] == "Black"


def test_cached_second_call_hits_no_bricklink(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    calls = []

    def once(no):
        calls.append(no)
        return _parts(no)

    monkeypatch.setattr(integrations, "bricklink_minifig_parts", once)
    client.get("/api/fig_parts/sw1213")
    client.get("/api/fig_parts/sw1213")
    assert len(calls) == 1          # zweiter Aufruf aus dem Cache


def test_empty_for_manual_or_rebrickable_number(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    assert client.get("/api/fig_parts/manuell-7").json()["items"] == []
    assert client.get("/api/fig_parts/fig-1234").json()["items"] == []


def test_empty_without_bricklink(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: False)
    assert client.get("/api/fig_parts/sw1213").json()["items"] == []


def test_missing_color_name_is_filled_from_bricklink(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(
        integrations, "bricklink_minifig_parts",
        lambda no: [{"item_id": "3626c", "item_type": "part", "name": "Kopf",
                     "color_id": 90, "color_name": "", "qty": 1,
                     "img_url": "", "bricklink_url": ""}])
    monkeypatch.setattr(integrations, "bricklink_colors",
                        lambda: {"90": "Light Nougat", "11": "Black"})
    main._color_cache.update(at=0, map={})      # Speicher-Cache leeren
    items = client.get("/api/fig_parts/sw1213").json()["items"]
    assert items[0]["color_name"] == "Light Nougat"


def test_color_map_cached_after_first_fetch(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(
        integrations, "bricklink_minifig_parts",
        lambda no: [{"item_id": "x", "item_type": "part", "name": "T",
                     "color_id": 5, "color_name": "", "qty": 1,
                     "img_url": "", "bricklink_url": ""}])
    calls = []

    def colors():
        calls.append(1)
        return {"5": "Red"}

    monkeypatch.setattr(integrations, "bricklink_colors", colors)
    main._color_cache.update(at=0, map={})
    client.get("/api/fig_parts/sw0001")
    client.get("/api/fig_parts/sw0002")
    assert len(calls) == 1          # Farbtabelle nur einmal geholt


def test_lookup_error_is_404(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)

    def boom(no):
        raise LookupError("Figur nicht gefunden")

    monkeypatch.setattr(integrations, "bricklink_minifig_parts", boom)
    assert client.get("/api/fig_parts/sw1213").status_code == 404
