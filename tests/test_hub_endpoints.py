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


def _add_item(item_id="sw1213", name="Yoda", qty=2, shared=0):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO collection (item_id, item_type, name, img_url, "
            "bricklink_url, quantity, condition, shared, added_at) VALUES "
            "(?, 'minifig', ?, 'i', 'b', ?, 'used', ?, ?)",
            (item_id, name, qty, shared, now))
        return cur.lastrowid


def test_publish_sends_only_chosen_items(client, monkeypatch):
    """Veröffentlicht wird die Auswahl – nicht automatisch alles Abgebbare."""
    _add_item("sw1213", "Yoda", qty=2, shared=1)
    _add_item("sw0552", "Vader", qty=3, shared=0)      # nicht ausgewählt
    captured = {}
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "publish",
                        lambda offers: captured.update(offers=offers) or {"count": len(offers)})
    r = client.post("/api/hub/publish")
    assert r.status_code == 200 and r.json()["count"] == 1
    o = captured["offers"][0]
    assert o["item_id"] == "sw1213" and o["name"] == "Yoda" and o["qty"] == 2


def test_publish_without_selection_is_empty(client, monkeypatch):
    _add_item(shared=0)
    captured = {}
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "publish",
                        lambda offers: captured.update(offers=offers) or {"count": 0})
    assert client.post("/api/hub/publish").json()["count"] == 0
    assert captured["offers"] == []


def test_share_toggle(client):
    eid = _add_item(shared=0)
    assert client.post(f"/api/collection/{eid}/share",
                       json={"shared": True}).status_code == 200
    assert client.get("/api/share/status").json()["shared"] == 1
    client.post(f"/api/collection/{eid}/share", json={"shared": False})
    assert client.get("/api/share/status").json()["shared"] == 0


def test_share_unknown_entry_404(client):
    assert client.post("/api/collection/999/share",
                       json={"shared": True}).status_code == 404


def test_share_from_duplicates_and_clear(client):
    _add_item("sw1213", "Yoda", qty=2)        # abgebbar: 1
    _add_item("sw0552", "Vader", qty=1)       # nicht abgebbar
    r = client.post("/api/share/from_duplicates").json()
    assert r["added"] == 1
    assert client.get("/api/share/status").json()["shared"] == 1
    client.post("/api/share/clear")
    assert client.get("/api/share/status").json()["shared"] == 0


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


def test_rename_endpoint_is_gone(client):
    """Umbenennen gehört in die Admin-Konsole, nicht in die App."""
    assert client.post("/api/hub/rename",
                       json={"display_name": "Sven"}).status_code == 404


def test_status_refresh_swallows_hub_errors(client, monkeypatch):
    monkeypatch.setattr(hub, "enabled", lambda: True)

    def boom():
        raise RuntimeError("Hub weg")
    monkeypatch.setattr(hub, "refresh", boom)
    # trotz Fehler beim Auffrischen liefert der Status 200
    assert client.get("/api/hub?refresh=1").status_code == 200


# ------------------------------------------------- Menge und Veröffentlichung

def test_share_qty_limits_published_amount(client, monkeypatch):
    """Von drei Yodas darf ich auch nur einen anbieten."""
    eid = _add_item("sw1213", "Yoda", qty=3)
    client.post(f"/api/collection/{eid}/share", json={"shared": True, "qty": 1})
    captured = {}
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "publish",
                        lambda offers: captured.update(offers=offers) or {"count": len(offers)})
    client.post("/api/hub/publish")
    assert captured["offers"][0]["qty"] == 1


def test_share_qty_cannot_exceed_stock(client):
    eid = _add_item("sw1213", "Yoda", qty=2)
    r = client.post(f"/api/collection/{eid}/share",
                    json={"shared": True, "qty": 9}).json()
    assert r["qty"] == 2


def test_share_qty_defaults_to_all(client, monkeypatch):
    eid = _add_item("sw1213", "Yoda", qty=4)
    client.post(f"/api/collection/{eid}/share", json={"shared": True})
    captured = {}
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "publish",
                        lambda offers: captured.update(offers=offers) or {"count": 1})
    client.post("/api/hub/publish")
    assert captured["offers"][0]["qty"] == 4


def test_share_status_marks_published_and_stale(client, monkeypatch):
    """Die Auswahl zeigt, was schon draußen ist – und was im Hub übrig blieb."""
    eid = _add_item("sw1213", "Yoda", qty=2)
    _add_item("sw0552", "Vader", qty=1, shared=1)
    client.post(f"/api/collection/{eid}/share", json={"shared": True, "qty": 1})
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "offers", lambda params=None: [
        {"item_id": "sw1213", "name": "Yoda", "qty": 1},
        {"item_id": "old1", "name": "Altes Angebot", "qty": 5},
    ])
    s = client.get("/api/share/status").json()
    assert s["known_state"] is True and s["published"] == 1
    by_id = {i["item_id"]: i for i in s["items"]}
    assert by_id["sw1213"]["published"] is True
    assert by_id["sw1213"]["published_qty"] == 1
    assert by_id["sw0552"]["published"] is False
    assert [o["item_id"] for o in s["stale"]] == ["old1"]


def test_share_status_without_hub_says_state_unknown(client, monkeypatch):
    _add_item("sw1213", "Yoda", qty=1, shared=1)
    monkeypatch.setattr(hub, "enabled", lambda: False)
    s = client.get("/api/share/status").json()
    assert s["known_state"] is False and s["stale"] == []


# ------------------------------------------------- Vorgänge löschen / entfallen

def _trade(tid="trd_a", direction="out"):
    with core.db() as conn:
        conn.execute(
            "INSERT INTO trades (id, direction, other_id, other_name, item_id,"
            " item_name, status, created_at, updated_at) VALUES "
            "(?, ?, 'mem_x', 'X', 'sw1', 'A', 'open', 1, 1)", (tid, direction))
        conn.execute("INSERT INTO trade_messages (trade_id, mine, body, "
                     "created_at) VALUES (?, 1, 'hallo', 1)", (tid,))


def test_delete_trade_removes_locally_and_in_hub(client, monkeypatch):
    _trade()
    monkeypatch.setattr(hub, "enabled", lambda: True)
    gone = []
    monkeypatch.setattr(hub, "delete_trade",
                        lambda tid: gone.append(tid) or {"ok": True})
    assert client.delete("/api/hub/trades/trd_a").status_code == 200
    assert gone == ["trd_a"]
    assert client.get("/api/hub/trades").json()["trades"] == []
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM trade_messages").fetchone()["c"] == 0


def test_delete_trade_tolerates_missing_hub_entry(client, monkeypatch):
    _trade()
    monkeypatch.setattr(hub, "enabled", lambda: True)

    def boom(tid):
        raise hub.HubError(404, "Vorgang nicht gefunden")
    monkeypatch.setattr(hub, "delete_trade", boom)
    assert client.delete("/api/hub/trades/trd_a").status_code == 200
    assert client.get("/api/hub/trades").json()["trades"] == []


def test_delete_trade_keeps_entry_when_hub_errors(client, monkeypatch):
    """Bei einem echten Hub-Fehler darf lokal nichts verschwinden – sonst wäre
    der Vorgang beim nächsten Abgleich wieder da, nur ohne Verlauf."""
    _trade()
    monkeypatch.setattr(hub, "enabled", lambda: True)

    def boom(tid):
        raise hub.HubError(500, "kaputt")
    monkeypatch.setattr(hub, "delete_trade", boom)
    assert client.delete("/api/hub/trades/trd_a").status_code == 502
    assert len(client.get("/api/hub/trades").json()["trades"]) == 1


def test_sync_marks_item_as_gone(client, monkeypatch):
    """Nimmt das Gegenüber das Angebot zurück, steht das am Vorgang."""
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "config", lambda: {
        "url": "h", "token": "t", "member_id": "mem_me",
        "display_name": "Ich", "is_admin": False})
    monkeypatch.setattr(hub, "put_key", lambda k: {"ok": True})
    monkeypatch.setattr(hub, "fetch_messages",
                        lambda tid: {"messages": [], "sent": []})
    base = {"id": "trd_a", "from_member": "mem_me", "to_member": "mem_x",
            "to_name": "X", "from_name": "Ich", "item_id": "sw1",
            "item_name": "A", "status": "open", "created_at": 1,
            "updated_at": 1, "unread": 0}
    monkeypatch.setattr(hub, "trades", lambda: [dict(base, item_available=1)])
    client.post("/api/hub/trades/sync")
    assert client.get("/api/hub/trades").json()["trades"][0]["item_gone"] == 0

    monkeypatch.setattr(hub, "trades", lambda: [dict(base, item_available=0)])
    client.post("/api/hub/trades/sync")
    assert client.get("/api/hub/trades").json()["trades"][0]["item_gone"] == 1


# ------------------------------------------------- sparsamer Abgleich

def test_sync_only_fetches_where_something_waits(client, monkeypatch):
    """Regelmäßiges Nachladen darf nicht für jeden Vorgang eine eigene
    Anfrage kosten – geholt wird nur, wo der Hub Post gemeldet hat."""
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "config", lambda: {
        "url": "h", "token": "t", "member_id": "mem_me",
        "display_name": "Ich", "is_admin": False})
    monkeypatch.setattr(hub, "put_key", lambda k: {"ok": True})
    monkeypatch.setattr(hub, "trades", lambda: [
        {"id": "trd_a", "from_member": "mem_me", "to_member": "mem_x",
         "to_name": "X", "from_name": "Ich", "item_id": "sw1", "item_name": "A",
         "status": "open", "created_at": 1, "updated_at": 1, "unread": 0},
        {"id": "trd_b", "from_member": "mem_y", "to_member": "mem_me",
         "to_name": "Ich", "from_name": "Y", "item_id": "sw2", "item_name": "B",
         "status": "open", "created_at": 1, "updated_at": 1, "unread": 2},
    ])
    fetched = []
    monkeypatch.setattr(hub, "fetch_messages",
                        lambda tid: fetched.append(tid) or {"messages": [], "sent": []})
    client.post("/api/hub/trades/sync")
    assert fetched == ["trd_b"]              # nur der mit Post

    fetched.clear()
    client.post("/api/hub/trades/sync?focus=trd_a")
    assert set(fetched) == {"trd_a", "trd_b"}   # offenes Gespräch kommt dazu
