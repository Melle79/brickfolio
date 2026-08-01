"""Angenommene Tausche verbuchen: /take (kommt rein) und /give (geht raus).

Bis 1.85.0 war „Annehmen" eine reine Zusage im Gespräch: Der Artikel landete
nirgends und musste von Hand nachgetragen werden. Hier steht, was seitdem
passiert – und was ausdrücklich nicht passieren darf. Beim Austragen (1.86.0)
zählt das doppelt: Dort verschwindet etwas, und ein geratener Zustand wäre ein
verlorenes Stück.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _user(is_dealer=1, name="sven"):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, 'x', 1, ?, ?)", (name, is_dealer, now))
        return cur.lastrowid


def _client(tmp_path, monkeypatch, is_dealer=1):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "take.db"))
    core.init_db()
    uid = _user(is_dealer)
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


@pytest.fixture
def client(tmp_path, monkeypatch):
    return _client(tmp_path, monkeypatch)


def _trade(tid="trd_1", direction="out", status="accepted", item_id="sw1213",
           name="Yoda", item_type="minifig", img="https://x.test/y.jpg",
           condition="used"):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO trades (id, direction, other_id, other_name, item_id,"
            " item_name, status, created_at, updated_at, item_type, img_url,"
            " bricklink_url, condition) VALUES (?, ?, 'm_paul', 'Paul', ?, ?,"
            " ?, ?, ?, ?, ?, '', ?)",
            (tid, direction, item_id, name, status, now, now, item_type, img,
             condition))
    return tid


def _sammlung():
    with core.db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM collection")]


def test_take_puts_item_into_collection(client):
    _trade()
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 200, r.text
    rows = _sammlung()
    assert len(rows) == 1
    assert rows[0]["item_id"] == "sw1213"
    assert rows[0]["item_type"] == "minifig"
    assert rows[0]["name"] == "Yoda"
    assert rows[0]["quantity"] == 1
    # Woher das Stück kam, steht in der Notiz – sonst weiß man es in einem
    # halben Jahr nicht mehr.
    assert "Paul" in rows[0]["notes"]


def test_take_records_quantity_condition_and_price(client):
    _trade()
    client.post("/api/hub/trades/trd_1/take", json={
        "ziel": "sammlung", "quantity": 3, "condition": "new",
        "paid_price": 12.5})
    row = _sammlung()[0]
    assert row["quantity"] == 3 and row["condition"] == "new"
    assert row["paid_price"] == 12.5
    with core.db() as conn:
        kauf = conn.execute("SELECT * FROM purchases").fetchall()
    assert len(kauf) == 1 and kauf[0]["quantity"] == 3


def test_take_marks_trade_as_taken(client):
    _trade()
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    t = client.get("/api/hub/trades/trd_1").json()["trade"]
    assert t["taken_at"] and t["taken_at"] > 0


def test_second_take_merges_instead_of_duplicating(client):
    _trade()
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.json()["ergebnis"]["merged"] is True
    rows = _sammlung()
    assert len(rows) == 1 and rows[0]["quantity"] == 2


def test_take_onto_shopping_list(client):
    _trade()
    lid = client.post("/api/lists", json={"name": "Abholen"}).json()["id"]
    r = client.post("/api/hub/trades/trd_1/take",
                    json={"ziel": "liste", "list_id": lid, "quantity": 2})
    assert r.status_code == 200, r.text
    items = client.get("/api/lists").json()["lists"][0]["items"]
    assert len(items) == 1 and items[0]["item_id"] == "sw1213"
    assert items[0]["qty"] == 2
    assert not _sammlung()          # nicht doppelt: Liste heißt nicht Sammlung


def test_take_needs_a_list_id_for_lists(client):
    _trade()
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "liste"})
    assert r.status_code == 400


def test_take_rejects_incoming_trades(client):
    """Eingehende Anfragen sind eigene Artikel, die weggehen."""
    _trade(direction="in")
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 400
    assert not _sammlung()


def test_take_rejects_open_trades(client):
    _trade(status="open")
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 400
    assert not _sammlung()


def test_take_unknown_trade_is_404(client):
    r = client.post("/api/hub/trades/trd_nix/take", json={"ziel": "sammlung"})
    assert r.status_code == 404


def test_lists_stay_closed_for_normal_users(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, is_dealer=0)
    _trade()
    r = c.post("/api/hub/trades/trd_1/take",
               json={"ziel": "liste", "list_id": 1})
    assert r.status_code == 403


def test_old_trade_without_type_guesses_set_from_number(client):
    """Vorgänge von vor 1.85.0 haben keine Art gespeichert."""
    _trade(item_id="21306-1", name="Yellow Submarine", item_type="")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["item_type"] == "set"


def test_old_trade_without_type_guesses_minifig(client):
    _trade(item_id="sw1213", item_type="")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["item_type"] == "minifig"


def test_trade_without_name_falls_back_to_number(client):
    _trade(name="")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["name"] == "sw1213"


def test_foreign_image_paths_are_not_taken_over(client):
    """`/uploads/…` zeigt auf die fremde Instanz – hier wäre es ein toter Link."""
    _trade(img="/uploads/fremd.jpg")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["img_url"] == ""


# ---------------------------------------------- Gegenstück: austragen (give)

def _sammlung_anlegen(client, item_id="sw1213", name="Yoda", qty=2,
                      condition="used"):
    r = client.post("/api/collection", json={
        "item_id": item_id, "item_type": "minifig", "name": name,
        "quantity": qty, "condition": condition})
    assert r.status_code == 200, r.text


def test_give_reduces_quantity(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=3)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 200, r.text
    assert r.json()["rest"] == 2 and r.json()["geloescht"] is False
    assert _sammlung()[0]["quantity"] == 2


def test_give_deletes_entry_when_nothing_is_left(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=1)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.json()["geloescht"] is True
    assert not _sammlung()


def test_give_takes_the_purchase_log_along(client):
    _trade(direction="in")
    client.post("/api/collection", json={
        "item_id": "sw1213", "item_type": "minifig", "name": "Yoda",
        "quantity": 1, "condition": "used", "paid_price": 9.0})
    client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0] == 0


def test_give_refuses_more_than_there_is(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=1)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 2})
    assert r.status_code == 400
    assert _sammlung()[0]["quantity"] == 1


def test_give_needs_a_condition_when_the_number_exists_twice(client):
    """Neu und gebraucht nebeneinander – raten wäre hier ein verlorenes Stück."""
    _trade(direction="in")
    _sammlung_anlegen(client, qty=1, condition="used")
    _sammlung_anlegen(client, qty=1, condition="new")
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 400
    assert len(_sammlung()) == 2
    r = client.post("/api/hub/trades/trd_1/give",
                    json={"quantity": 1, "condition": "new"})
    assert r.status_code == 200
    rest = _sammlung()
    assert len(rest) == 1 and rest[0]["condition"] == "used"


def test_give_rejects_outgoing_trades(client):
    _trade(direction="out")
    _sammlung_anlegen(client)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 400
    assert _sammlung()[0]["quantity"] == 2


def test_give_rejects_trades_that_are_not_accepted(client):
    _trade(direction="in", status="open")
    _sammlung_anlegen(client)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 400


def test_give_without_the_item_in_the_collection_is_404(client):
    _trade(direction="in")
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 404


def test_give_marks_the_trade(client):
    _trade(direction="in")
    _sammlung_anlegen(client)
    client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert client.get("/api/hub/trades/trd_1").json()["trade"]["taken_at"]


def test_candidates_list_both_conditions(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=2, condition="used")
    _sammlung_anlegen(client, qty=1, condition="new")
    k = client.get("/api/hub/trades/trd_1/candidates").json()["candidates"]
    assert [(c["condition"], c["quantity"]) for c in k] \
        == [("new", 1), ("used", 2)]


def test_candidates_are_empty_when_nothing_matches(client):
    _trade(direction="in")
    assert client.get("/api/hub/trades/trd_1/candidates").json()["candidates"] \
        == []
