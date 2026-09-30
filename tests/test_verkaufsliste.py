"""Verkaufslisten (3.3.0): Abhaken nimmt die Stücke aus der Sammlung heraus.

Das Gegenteil des Wareneingangs – mit Kaufbuch, und „Rückgängig“ legt alles
genau so zurück, wie es war.
"""
import time

import pytest
from fastapi.testclient import TestClient

import core
import main


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "d.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        profi = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)", (now,)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(profi, "admin", True)
    return c


def _figur(c, nr="sw0001", menge=3, preis=9.0, zustand="used"):
    r = c.post("/api/collection", json={"item_id": nr, "item_type": "minifig",
                                        "name": "Figur " + nr, "quantity": menge,
                                        "condition": zustand, "paid_price": preis})
    assert r.status_code == 200, r.text
    with core.db() as conn:
        return dict(conn.execute("SELECT * FROM collection WHERE item_id = ?",
                                 (nr,)).fetchone())


def _verkaufsliste(c, name="Verkauf Olli"):
    lid = c.post("/api/lists", json={"name": name}).json()["id"]
    r = c.post(f"/api/lists/{lid}/rename", json={"name": name, "art": "verkauf"})
    assert r.status_code == 200
    return lid


def _auf_liste(c, lid, nr="sw0001", menge=1, zustand="used"):
    c.post(f"/api/lists/{lid}/items", json={
        "item_id": nr, "item_type": "minifig", "name": "Figur " + nr,
        "qty": menge, "condition": zustand})
    with core.db() as conn:
        return conn.execute("SELECT id FROM shopping_items WHERE list_id = ? "
                            "AND item_id = ?", (lid, nr)).fetchone()["id"]


def _zeile(nr="sw0001"):
    with core.db() as conn:
        z = conn.execute("SELECT * FROM collection WHERE item_id = ?",
                         (nr,)).fetchone()
        return dict(z) if z else None


def _buch(eid):
    with core.db() as conn:
        return [(r["quantity"], r["unit_price"]) for r in conn.execute(
            "SELECT quantity, unit_price FROM purchases WHERE entry_id = ? "
            "ORDER BY id", (eid,))]


def test_stift_stellt_auf_verkaufsliste(ctx):
    c = ctx
    lid = _verkaufsliste(c)
    liste = c.get("/api/lists").json()["lists"][0]
    assert liste["id"] == lid and liste["art"] == "verkauf"
    # Umbenennen ohne Art lässt sie, wie sie ist.
    c.post(f"/api/lists/{lid}/rename", json={"name": "Neu"})
    assert c.get("/api/lists").json()["lists"][0]["art"] == "verkauf"


def test_teilverkauf_nimmt_stuecke_und_kaufbuch_mit(ctx):
    c = ctx
    e = _figur(c, menge=3, preis=9.0)
    lid = _verkaufsliste(c)
    iid = _auf_liste(c, lid, menge=2)
    r = c.post(f"/api/lists/items/{iid}/receive",
               json={"condition": "used", "paid_price": 12.0})
    assert r.status_code == 200 and r.json()["sold"] is True
    z = _zeile()
    assert z["quantity"] == 1 and z["paid_price"] == 3.0
    assert "verkauft über Liste »Verkauf Olli«" in z["notes"]
    with core.db() as conn:
        it = conn.execute("SELECT * FROM shopping_items WHERE id = ?",
                          (iid,)).fetchone()
    assert it["done"] == 1 and it["recv_mode"] == "verkauft" and it["paid_price"] == 12.0
    # Rückgängig: Menge, Kaufbuch und Notiz wie vorher.
    assert c.post(f"/api/lists/items/{iid}/undo").json()["reverted"] is True
    z = _zeile()
    assert z["quantity"] == 3 and z["paid_price"] == 9.0 and not z["notes"]
    assert _buch(e["id"]) == [(3, 3.0)]


def test_letztes_stueck_verkauft_zeile_weg_und_zurueck(ctx):
    c = ctx
    _figur(c, menge=1, preis=5.0)
    lid = _verkaufsliste(c)
    iid = _auf_liste(c, lid, menge=1)
    assert c.post(f"/api/lists/items/{iid}/receive",
                  json={"condition": "used"}).status_code == 200
    assert _zeile() is None
    # Liste mit dem letzten Artikel abgearbeitet → Archiv, wie beim Einkauf.
    with core.db() as conn:
        assert conn.execute("SELECT archived FROM shopping_lists WHERE id = ?",
                            (lid,)).fetchone()["archived"] == 1
    assert c.post(f"/api/lists/items/{iid}/undo").json()["reverted"] is True
    z = _zeile()
    assert z and z["quantity"] == 1 and z["paid_price"] == 5.0
    assert _buch(z["id"]) == [(1, 5.0)]


def test_nicht_in_der_sammlung(ctx):
    c = ctx
    lid = _verkaufsliste(c)
    iid = _auf_liste(c, lid)
    r = c.post(f"/api/lists/items/{iid}/receive", json={"condition": "used"})
    assert r.status_code == 409 and "Nicht in der Sammlung" in r.text
    # Falscher Zustand zählt auch als „nicht da“.
    _figur(c, zustand="new")
    assert c.post(f"/api/lists/items/{iid}/receive",
                  json={"condition": "used"}).status_code == 409


def test_zu_wenig_stueck(ctx):
    c = ctx
    _figur(c, menge=1)
    lid = _verkaufsliste(c)
    iid = _auf_liste(c, lid, menge=2)
    r = c.post(f"/api/lists/items/{iid}/receive", json={"condition": "used"})
    assert r.status_code == 409 and "nur 1 Stück" in r.text
    assert _zeile()["quantity"] == 1


def test_einkaufsliste_bleibt_wie_sie_war(ctx):
    c = ctx
    lid = c.post("/api/lists", json={"name": "Flohmarkt"}).json()["id"]
    assert c.get("/api/lists").json()["lists"][0]["art"] == "einkauf"
    iid = _auf_liste(c, lid)
    c.post(f"/api/lists/items/{iid}/receive", json={"condition": "used"})
    assert _zeile()["quantity"] == 1


def test_erloes_zaehlt_nicht_als_einkauf(ctx):
    """Die Statistik rechnet Einkaufspreise auf Listen zusammen – der Erlös
    einer Verkaufsliste gehört nicht dazu."""
    c = ctx
    _figur(c, menge=2)
    lid = _verkaufsliste(c)
    iid = _auf_liste(c, lid)
    c.post(f"/api/lists/items/{iid}/receive", json={"condition": "used",
                                                     "paid_price": 20.0})
    # Gegenprobe: eine Einkaufsliste mit Preis taucht auf.
    ek = c.post("/api/lists", json={"name": "Flohmarkt"}).json()["id"]
    c.post(f"/api/lists/{ek}/items", json={
        "item_id": "sw0009", "item_type": "minifig", "name": "X", "qty": 1,
        "condition": "used", "paid_price": 4.0})
    namen = [x["name"] for x in
             c.get("/api/stats/dashboard").json()["lists_breakdown"]]
    assert "Flohmarkt" in namen and "Verkauf Olli" not in namen
