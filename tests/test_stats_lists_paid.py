"""Test für das neue Statistik-Feld: Summe der Einkaufspreise über alle
offenen Einkaufslisten (totals.lists_paid)."""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "s.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('finn', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "finn", True)
    c.uid = uid
    return c


def _list(uid, name="Flohmarkt", archived=0):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO shopping_lists (name, archived, created_by, created_at)"
            " VALUES (?, ?, ?, ?)", (name, archived, uid, now))
        return cur.lastrowid


def _item(list_id, paid_price=None, qty=1):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name, qty,"
            " condition, paid_price, done, added_at) VALUES "
            "(?, 'sw0001', 'minifig', 'X', ?, 'used', ?, 0, ?)",
            (list_id, qty, paid_price, now))


def test_sums_paid_across_open_lists(client):
    l1 = _list(client.uid, "A")
    l2 = _list(client.uid, "B")
    _item(l1, 4.50)
    _item(l1, 5.50)
    _item(l2, 10.00)
    _item(l1, None)          # ohne Preis -> zählt nicht
    t = client.get("/api/stats/dashboard").json()["totals"]
    assert t["lists_paid"] == 20.0
    assert t["lists_count"] == 2


def test_archived_lists_are_excluded(client):
    live = _list(client.uid, "offen")
    old = _list(client.uid, "archiviert", archived=1)
    _item(live, 7.00)
    _item(old, 99.00)
    t = client.get("/api/stats/dashboard").json()["totals"]
    assert t["lists_paid"] == 7.0
    assert t["lists_count"] == 1


def test_zero_without_lists(client):
    t = client.get("/api/stats/dashboard").json()["totals"]
    assert t["lists_paid"] == 0
    assert t["lists_count"] == 0
