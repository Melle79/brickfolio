"""Tests für die Wertangaben der Sammlung (Issue #11).

Kern: Was die Oberfläche je Eintrag summiert (Themenkarten), muss mit der
Kopfsumme zusammenpassen. Figuren, die in eigenen Sets stecken, sind im
Set-Preis enthalten und dürfen nicht doppelt zählen.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "v.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def _add(item_id, name, item_type="minifig", qty=1, price_used=None,
         theme=None, condition="used"):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, price_used, theme, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, item_type, name, qty, condition, price_used, theme, now))


def _contents(set_no, fig_no, qty=1):
    with core.db() as conn:
        conn.execute("INSERT INTO set_contents (set_no, fig_no, qty) "
                     "VALUES (?, ?, ?)", (set_no, fig_no, qty))


def test_each_item_reports_its_value(client):
    _add("sw0001", "Luke", price_used=10.0, qty=3)
    it = client.get("/api/collection").json()["items"][0]
    assert it["unit_price"] == 10.0
    assert it["value"] == 30.0
    assert it["net_value"] == 30.0        # nichts in Sets gebunden
    assert it["bound_qty"] == 0


def test_figure_inside_own_set_is_not_counted_twice(client):
    """Der Kern des gemeldeten Fehlers: Die Figur steckt im eigenen Set."""
    _add("75300-1", "TIE Fighter", item_type="set", price_used=100.0)
    _add("sw1155", "Pilot", price_used=8.0, qty=1)
    _contents("75300-1", "sw1155", qty=1)

    data = client.get("/api/collection").json()
    by_id = {i["item_id"]: i for i in data["items"]}
    pilot = by_id["sw1155"]
    assert pilot["value"] == 8.0          # für sich genommen 8 €
    assert pilot["bound_qty"] == 1
    assert pilot["net_value"] == 0.0      # steckt im Set – zählt nicht extra
    assert data["stats"]["total_value"] == 100.0


def test_group_sums_match_header(client):
    """Summiert man die Einträge wie die Themenkarten, muss die Kopfsumme
    herauskommen – genau das stimmte vorher nicht."""
    _add("75300-1", "TIE Fighter", item_type="set", price_used=100.0,
         theme="Star Wars")
    _add("sw1155", "Pilot", price_used=8.0, qty=2, theme="Star Wars")
    _contents("75300-1", "sw1155", qty=1)          # 1 von 2 steckt im Set
    _add("cty0001", "Polizist", price_used=5.0, theme="City")

    data = client.get("/api/collection").json()
    summe = sum(i["net_value"] or 0 for i in data["items"])
    assert summe == pytest.approx(data["stats"]["total_value"])
    assert summe == pytest.approx(100.0 + 8.0 + 5.0)   # eine Figur gebunden


def test_unpriced_items_have_no_value(client):
    _add("sw0001", "Ohne Preis")
    it = client.get("/api/collection").json()["items"][0]
    assert it["value"] is None and it["net_value"] is None


def test_type_filter_keeps_full_figure_value(client):
    """Mit Filter „Figuren" steht der volle Figurenwert – wie im Kopf auch."""
    _add("75300-1", "TIE Fighter", item_type="set", price_used=100.0)
    _add("sw1155", "Pilot", price_used=8.0)
    _contents("75300-1", "sw1155", qty=1)

    data = client.get("/api/collection?item_type=minifig").json()
    pilot = data["items"][0]
    assert pilot["net_value"] == 8.0
    assert sum(i["net_value"] or 0 for i in data["items"]) == pytest.approx(
        data["stats"]["total_value"])


def test_new_condition_uses_new_price(client):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, price_new, price_used, added_at) VALUES "
            "('sw0001', 'minifig', 'Luke', 2, 'new', 20.0, 10.0, ?)", (now,))
    it = client.get("/api/collection").json()["items"][0]
    assert it["unit_price"] == 20.0 and it["value"] == 40.0
