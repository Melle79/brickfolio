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
    def fake_connect(token):
        core.set_setting("hub_token", token)
        core.set_setting("hub_display_name", "Sven")
        core.set_setting("hub_is_admin", "1")
        return {"display_name": "Sven", "is_admin": True}
    monkeypatch.setattr(hub, "connect_with_token", fake_connect)
    r = client.post("/api/hub/connect", json={"token": "bft_x"})
    assert r.status_code == 200
    s = client.get("/api/hub").json()
    assert s["connected"] is True and s["display_name"] == "Sven"
    assert s["is_admin"] is True


def test_connect_requires_token_or_invite(client):
    r = client.post("/api/hub/connect", json={})
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
    core.set_setting("hub_token", "t")
    core.set_setting("hub_display_name", "Sven")
    client.post("/api/hub/disconnect")
    assert (core.get_setting("hub_token") or "") == ""
    assert hub.enabled() is False


def test_hub_management_is_admin_only(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "hub2.db"))
    core.init_db()
    uid = _user(is_admin=0, is_dealer=1, name="paul")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "paul", False)
    assert c.post("/api/hub/publish").status_code == 403
    assert c.post("/api/hub/connect",
                  json={"url": "https://h", "token": "t"}).status_code == 403


def test_invite_allowed_for_any_connected_user(monkeypatch, tmp_path):
    # Auch ein Nicht-Instanz-Admin darf einladen, solange verbunden.
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "hub3.db"))
    core.init_db()
    uid = _user(is_admin=0, is_dealer=0, name="lena")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "lena", False)
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "create_invite",
                        lambda note="", expires_in_days=0: {"invite_code": "inv_x"})
    r = c.post("/api/hub/invite", json={})
    assert r.status_code == 200 and r.json()["invite_code"] == "inv_x"


def test_invite_without_connection_400(client, monkeypatch):
    monkeypatch.setattr(hub, "enabled", lambda: False)
    assert client.post("/api/hub/invite", json={}).status_code == 400


def test_rename_updates_display_name(client, monkeypatch):
    monkeypatch.setattr(hub, "enabled", lambda: True)

    def fake_rename(name):
        core.set_setting("hub_display_name", name)
        return {"display_name": name}
    monkeypatch.setattr(hub, "rename", fake_rename)
    r = client.post("/api/hub/rename", json={"display_name": "Sven"})
    assert r.status_code == 200 and r.json()["display_name"] == "Sven"


def test_rename_without_connection_400(client, monkeypatch):
    monkeypatch.setattr(hub, "enabled", lambda: False)
    assert client.post("/api/hub/rename",
                       json={"display_name": "Sven"}).status_code == 400


def test_status_refresh_swallows_hub_errors(client, monkeypatch):
    monkeypatch.setattr(hub, "enabled", lambda: True)

    def boom():
        raise RuntimeError("Hub weg")
    monkeypatch.setattr(hub, "refresh", boom)
    # trotz Fehler beim Auffrischen liefert der Status 200
    assert client.get("/api/hub?refresh=1").status_code == 200
