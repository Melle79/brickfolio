"""Tests für /api/missing_set_figs – welche Figuren fehlen über alle
eigenen Sets hinweg. Rechnet Bedarf (Set-Inhalt × besessene Sets) minus
Bestand und ist damit die fehleranfälligste der neueren Funktionen.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


class Api:
    def __init__(self, client):
        self.client = client

    def add_set(self, item_id, name, quantity=1, condition="used"):
        with core.db() as conn:
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity, "
                "condition, added_at) VALUES (?, 'set', ?, ?, ?, ?)",
                (item_id, name, quantity, condition, int(time.time())))

    def add_fig(self, item_id, name, quantity=1, condition="used"):
        with core.db() as conn:
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity, "
                "condition, added_at) VALUES (?, 'minifig', ?, ?, ?, ?)",
                (item_id, name, quantity, condition, int(time.time())))

    def add_contents(self, set_no, fig_no, qty=1, name=None, img_url=None):
        with core.db() as conn:
            conn.execute(
                "INSERT INTO set_contents (set_no, fig_no, qty, name, img_url) "
                "VALUES (?, ?, ?, ?, ?)", (set_no, fig_no, qty, name, img_url))

    def add_wanted(self, item_id, name, price_new=None, price_used=None):
        with core.db() as conn:
            conn.execute(
                "INSERT INTO wanted (item_id, item_type, name, price_new, "
                "price_used, added_at) VALUES (?, 'minifig', ?, ?, ?, ?)",
                (item_id, name, price_new, price_used, int(time.time())))

    def add_price_history(self, item_id, price_new, price_used):
        with core.db() as conn:
            conn.execute(
                "INSERT INTO price_history (item_id, item_type, ts, price_new, "
                "price_used) VALUES (?, 'minifig', ?, ?, ?)",
                (item_id, int(time.time()), price_new, price_used))

    def get(self):
        r = self.client.get("/api/missing_set_figs")
        assert r.status_code == 200, r.text
        return r.json()

    def by_id(self, data, item_id):
        return next((i for i in data["items"] if i["item_id"] == item_id), None)


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "missing.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer, "
            "created_at) VALUES ('tester', 'x', 0, 1, ?)", (now,))
        uid = cur.lastrowid
    client = TestClient(main.app)
    client.headers["Authorization"] = (
        "Bearer " + core.create_token(uid, "tester", False))
    return Api(client)


def test_no_sets_yields_empty(api):
    data = api.get()
    assert data["items"] == []
    assert data["stats"]["sets_total"] == 0


def test_complete_set_is_not_listed(api):
    api.add_set("75318-1", "The Child")
    api.add_contents("75318-1", "sw1113", qty=1, name="Din Grogu")
    api.add_fig("sw1113", "Din Grogu", quantity=1)
    data = api.get()
    assert data["items"] == []
    assert data["stats"]["sets_incomplete"] == 0


def test_missing_figure_is_listed_with_set(api):
    api.add_set("75318-1", "The Child")
    api.add_contents("75318-1", "sw1113", qty=1, name="Din Grogu")
    data = api.get()
    item = api.by_id(data, "sw1113")
    assert item is not None
    assert item["missing"] == 1 and item["needed"] == 1 and item["owned"] == 0
    assert item["sets"] == [{"no": "75318-1", "name": "The Child", "qty": 1}]


def test_need_scales_with_owned_set_quantity(api):
    # 2 Exemplare des Sets, je 2 Piloten enthalten -> Bedarf 4
    api.add_set("75300-1", "TIE Fighter", quantity=2)
    api.add_contents("75300-1", "sw1155", qty=2, name="Pilot")
    api.add_fig("sw1155", "Pilot", quantity=1)
    item = api.by_id(api.get(), "sw1155")
    assert item["needed"] == 4 and item["owned"] == 1 and item["missing"] == 3


def test_same_figure_in_two_sets_accumulates(api):
    api.add_set("A-1", "Set A")
    api.add_set("B-1", "Set B")
    api.add_contents("A-1", "sw0001", qty=1, name="Fig")
    api.add_contents("B-1", "sw0001", qty=1, name="Fig")
    item = api.by_id(api.get(), "sw0001")
    assert item["needed"] == 2 and item["missing"] == 2
    assert {s["no"] for s in item["sets"]} == {"A-1", "B-1"}


def test_price_and_wanted_flag_from_wishlist(api):
    api.add_set("75318-1", "The Child")
    api.add_contents("75318-1", "sw1113", qty=1, name="Din Grogu")
    api.add_wanted("sw1113", "Din Grogu", price_new=3.0, price_used=2.0)
    item = api.by_id(api.get(), "sw1113")
    assert item["wanted"] is True
    assert item["price_used"] == 2.0 and item["unit_price"] == 2.0


def test_price_falls_back_to_price_history(api):
    api.add_set("75300-1", "TIE Fighter")
    api.add_contents("75300-1", "sw0036", qty=1, name="Stormtrooper")
    api.add_price_history("sw0036", 9.5, 6.0)
    item = api.by_id(api.get(), "sw0036")
    assert item["wanted"] is False and item["unit_price"] == 6.0


def test_name_falls_back_when_contents_have_none(api):
    """Altbestand: Set-Inhalt ohne Namen -> Name aus der Sammlung."""
    api.add_set("75300-1", "TIE Fighter", quantity=2)
    api.add_contents("75300-1", "sw1155", qty=2)          # kein Name
    api.add_fig("sw1155", "Imperial Pilot", quantity=1)
    data = api.get()
    item = api.by_id(data, "sw1155")
    assert item["name"] == "Imperial Pilot"
    assert data["stats"]["details_pending"] == 1     # Set braucht Details


def test_name_is_number_when_nothing_known(api):
    api.add_set("75300-1", "TIE Fighter")
    api.add_contents("75300-1", "sw9999", qty=1)          # kein Name, unbekannt
    item = api.by_id(api.get(), "sw9999")
    assert item["name"] == "sw9999"


def test_stats_sum_up(api):
    api.add_set("75318-1", "The Child")
    api.add_set("75300-1", "TIE Fighter")
    api.add_contents("75318-1", "sw1113", qty=1, name="Din Grogu")
    api.add_contents("75300-1", "sw0036", qty=2, name="Stormtrooper")
    api.add_wanted("sw1113", "Din Grogu", price_used=2.0)
    api.add_price_history("sw0036", 9.5, 6.0)
    s = api.get()["stats"]
    assert s["figs"] == 2                 # zwei verschiedene Figuren
    assert s["pieces"] == 3               # 1 + 2 Exemplare
    assert s["est_cost"] == 14.0          # 1×2,00 + 2×6,00
    assert s["sets_incomplete"] == 2 and s["sets_total"] == 2


def test_sorted_by_name(api):
    api.add_set("A-1", "Set A")
    api.add_contents("A-1", "sw0002", qty=1, name="Zeta")
    api.add_contents("A-1", "sw0001", qty=1, name="Alpha")
    names = [i["name"] for i in api.get()["items"]]
    assert names == ["Alpha", "Zeta"]
