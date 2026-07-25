"""Tests für die Instanz-Seite des Tausch-Hubs (/api/hub…).

Der Hub-Client (hub.*) wird gemockt – hier geht es um Verdrahtung, Rechte
und das Ableiten der Angebote aus dem Abgebbar-Bestand.
"""
import time

import pytest

import core
import hub
import main
from fastapi.testclient import TestClient


def _user(is_admin=1, is_dealer=1, name="sven"):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, 'x', ?, ?, ?)", (name, is_admin, is_dealer, now))
        return cur.lastrowid


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "hub.db"))
    core.init_db()
    uid = _user()
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_status_when_not_connected(client):
    s = client.get("/api/hub").json()
    assert s["connected"] is False and s["display_name"] == ""


def test_connect_with_token_sets_status(client, monkeypatch):
    def fake_connect(url, token):
        core.set_setting("hub_url", url)
        core.set_setting("hub_token", token)
        core.set_setting("hub_display_name", "Sven")
        core.set_setting("hub_is_admin", "1")
        return {"display_name": "Sven", "is_admin": True}
    monkeypatch.setattr(hub, "connect_with_token", fake_connect)
    r = client.post("/api/hub/connect",
                    json={"url": "https://h.example", "token": "bft_x"})
    assert r.status_code == 200
    s = client.get("/api/hub").json()
    assert s["connected"] is True and s["display_name"] == "Sven"
    assert s["is_admin"] is True


def test_connect_rejects_bad_url(client):
    r = client.post("/api/hub/connect",
                    json={"url": "ftp://example.com", "token": "t"})
    assert r.status_code == 400


def test_connect_requires_token_or_invite(client):
    r = client.post("/api/hub/connect", json={"url": "https://h.example"})
    assert r.status_code == 400


def test_publish_maps_duplicates_to_offers(client, monkeypatch):
    # Ein Duplikat (Menge 2 -> 1 abgebbar) anlegen
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, img_url, "
            "bricklink_url, quantity, condition, added_at) VALUES "
            "('sw1213', 'minifig', 'Yoda', 'i', 'b', 2, 'used', ?)", (now,))
    captured = {}
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "publish",
                        lambda offers: captured.update(offers=offers) or {"count": len(offers)})
    r = client.post("/api/hub/publish")
    assert r.status_code == 200 and r.json()["count"] == 1
    o = captured["offers"][0]
    assert o["item_id"] == "sw1213" and o["qty"] == 1 and o["name"] == "Yoda"


def test_publish_without_connection_400(client, monkeypatch):
    monkeypatch.setattr(hub, "enabled", lambda: False)
    assert client.post("/api/hub/publish").status_code == 400


def test_disconnect_clears(client, monkeypatch):
    core.set_setting("hub_url", "https://h")
    core.set_setting("hub_token", "t")
    client.post("/api/hub/disconnect")
    assert (core.get_setting("hub_url") or "") == ""


def test_hub_management_is_admin_only(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "hub2.db"))
    core.init_db()
    uid = _user(is_admin=0, is_dealer=1, name="paul")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "paul", False)
    assert c.post("/api/hub/publish").status_code == 403
    assert c.post("/api/hub/connect",
                  json={"url": "https://h", "token": "t"}).status_code == 403


def test_invite_needs_hub_admin(client, monkeypatch):
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "config", lambda: {"url": "h", "token": "t",
                        "member_id": "m", "display_name": "Sven", "is_admin": False})
    assert client.post("/api/hub/invite", json={}).status_code == 403
