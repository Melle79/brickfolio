"""Integrationstests für den komplexesten Schreibpfad: einen Einkaufslisten-
Artikel »erhalten« (in die Sammlung verschieben) und wieder rückgängig machen.

Fährt den echten FastAPI-Endpoint über den TestClient gegen eine frische
SQLite-DB pro Test. Ohne BrickLink-Keys laufen keine Netzwerkabrufe.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


class Api:
    def __init__(self, client, uid):
        self.client = client
        self.uid = uid

    def new_list(self, name="Flohmarkt", archived=0):
        now = int(time.time())
        with core.db() as conn:
            cur = conn.execute(
                "INSERT INTO shopping_lists (name, archived, created_by, "
                "created_at) VALUES (?, ?, ?, ?)", (name, archived, self.uid, now))
            return cur.lastrowid

    def add_item(self, list_id, item_id="sw0001a", item_type="minifig",
                 name="Luke", qty=1, condition="used", price_new=None,
                 price_used=None, paid_price=None, done=0):
        now = int(time.time())
        with core.db() as conn:
            cur = conn.execute(
                "INSERT INTO shopping_items (list_id, item_id, item_type, "
                "name, qty, condition, price_new, price_used, paid_price, "
                "done, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (list_id, item_id, item_type, name, qty, condition,
                 price_new, price_used, paid_price, done, now))
            return cur.lastrowid

    def add_collection(self, item_id="sw0001a", item_type="minifig",
                       name="Luke", qty=1, condition="used", paid_price=None):
        now = int(time.time())
        with core.db() as conn:
            cur = conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity, "
                "condition, paid_price, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (item_id, item_type, name, qty, condition, paid_price, now))
            return cur.lastrowid

    def receive(self, item_id, **body):
        return self.client.post(f"/api/lists/items/{item_id}/receive", json=body)

    def undo(self, item_id):
        return self.client.post(f"/api/lists/items/{item_id}/undo")

    def collection_row(self, item_id, condition):
        with core.db() as conn:
            return conn.execute(
                "SELECT * FROM collection WHERE item_id = ? AND condition = ?",
                (item_id, condition)).fetchone()

    def item_row(self, item_id):
        with core.db() as conn:
            return conn.execute("SELECT * FROM shopping_items WHERE id = ?",
                                (item_id,)).fetchone()

    def list_row(self, list_id):
        with core.db() as conn:
            return conn.execute("SELECT * FROM shopping_lists WHERE id = ?",
                                (list_id,)).fetchone()


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "it.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer, "
            "created_at) VALUES ('tester', 'x', 0, 1, ?)", (now,))
        uid = cur.lastrowid
    token = core.create_token(uid, "tester", False)
    client = TestClient(main.app)
    client.headers["Authorization"] = f"Bearer {token}"
    return Api(client, uid)


def test_receive_new_item_creates_collection_entry(api):
    lid = api.new_list()
    iid = api.add_item(lid, qty=2, condition="used", price_used=5.0)
    r = api.receive(iid, condition="used")
    assert r.status_code == 200 and r.json()["ok"] is True

    row = api.collection_row("sw0001a", "used")
    assert row is not None
    assert row["quantity"] == 2
    # Auto-Kaufpreis = Ø-Preis × Menge
    assert row["paid_price"] == 10.0
    assert row["paid_source"] == "auto"
    # Herkunft steht in den Notizen
    assert "Von Liste »Flohmarkt«" in (row["notes"] or "")
    # Artikel ist erledigt
    assert api.item_row(iid)["done"] == 1


def test_receive_existing_without_mode_asks_for_mode(api):
    api.add_collection(qty=1, condition="used")
    lid = api.new_list()
    iid = api.add_item(lid, qty=1, condition="used", price_used=5.0)
    r = api.receive(iid, condition="used")
    body = r.json()
    assert body["ok"] is False and body["need_mode"] is True
    assert body["owned"] == 1
    # Nichts wurde verbucht
    assert api.item_row(iid)["done"] == 0


def test_receive_add_mode_increases_quantity_and_averages_paid(api):
    api.add_collection(qty=1, condition="used", paid_price=4.0)
    lid = api.new_list()
    iid = api.add_item(lid, qty=2, condition="used", price_used=5.0)
    r = api.receive(iid, condition="used", mode="add")
    assert r.status_code == 200
    row = api.collection_row("sw0001a", "used")
    assert row["quantity"] == 3            # 1 + 2
    # Ø aus vorhandenem (4.0) und neuem (5*2=10) Kaufpreis
    assert row["paid_price"] == 7.0


def test_receive_replace_mode_overwrites_quantity(api):
    api.add_collection(qty=5, condition="used")
    lid = api.new_list()
    iid = api.add_item(lid, qty=2, condition="used", price_used=5.0)
    r = api.receive(iid, condition="used", mode="replace")
    assert r.status_code == 200
    assert api.collection_row("sw0001a", "used")["quantity"] == 2


def test_receive_already_done_conflicts(api):
    lid = api.new_list()
    iid = api.add_item(lid, done=1)
    r = api.receive(iid, condition="used")
    assert r.status_code == 409


def test_undo_reopens_item_and_unarchives_list(api):
    lid = api.new_list()
    iid = api.add_item(lid, qty=1, condition="used", price_used=5.0)
    api.receive(iid, condition="used")
    # Einziger Artikel erledigt -> Liste wurde automatisch archiviert
    assert api.list_row(lid)["archived"] == 1

    r = api.undo(iid)
    assert r.status_code == 200
    assert api.item_row(iid)["done"] == 0
    # Liste ist wieder offen
    assert api.list_row(lid)["archived"] == 0


def test_dealer_manual_paid_price_is_honored(api):
    lid = api.new_list()
    iid = api.add_item(lid, qty=1, condition="used", price_used=5.0)
    r = api.receive(iid, condition="used", paid_price=2.5)
    assert r.status_code == 200
    row = api.collection_row("sw0001a", "used")
    assert row["paid_price"] == 2.5
    assert row["paid_source"] == "manual"
