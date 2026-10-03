"""Verkaufslisten im Tausch-Netzwerk (3.4.0).

Eine Verkaufsliste lässt sich ins Netz stellen: Ihre offenen Artikel werden
in der Sammlung als Verkauf angeboten, mit Preis je Stück. Liste und Netz
wissen voneinander – wer auf der Liste abhakt, zieht das Angebot zurück; wer
über das Netz verkauft und austrägt, hakt die Liste ab.
"""
import time

import pytest
from fastapi.testclient import TestClient

import core
import main
import community  # noqa: E402 – erst nach main, sonst Zirkel-Import
import hub


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "n.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('anna', 'x', 1, 1, ?)", (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    gesendet = []
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "publish", lambda offers: gesendet.append(offers) or {"count": len(offers)})
    monkeypatch.setattr(hub, "last_publish", lambda: {"ts": 1})
    monkeypatch.setattr(hub, "trade_progress", lambda tid, step: {"ok": True})
    return c, gesendet


def _figur(c, nr="sw0001", menge=3, zustand="used"):
    c.post("/api/collection", json={"item_id": nr, "item_type": "minifig",
                                    "name": "Figur " + nr, "quantity": menge,
                                    "condition": zustand})
    with core.db() as conn:
        conn.execute("UPDATE collection SET price_used = 5.0, price_new = 9.0 "
                     "WHERE item_id = ?", (nr,))


def _liste(c, art="verkauf"):
    lid = c.post("/api/lists", json={"name": "Verkauf"}).json()["id"]
    c.post(f"/api/lists/{lid}/rename", json={"name": "Verkauf", "art": art})
    return lid


def _artikel(c, lid, nr="sw0001", menge=2, zustand="used", erloes=None):
    c.post(f"/api/lists/{lid}/items", json={
        "item_id": nr, "item_type": "minifig", "name": "Figur " + nr,
        "qty": menge, "condition": zustand, "paid_price": erloes})
    with core.db() as conn:
        conn.execute("UPDATE shopping_items SET price_used = 5.0, price_new = 9.0")
        return conn.execute("SELECT id FROM shopping_items WHERE list_id = ? AND "
                            "item_id = ?", (lid, nr)).fetchone()["id"]


def _zeile(nr="sw0001"):
    with core.db() as conn:
        r = conn.execute("SELECT * FROM collection WHERE item_id = ?", (nr,)).fetchone()
        return dict(r) if r else None


def test_verkaufsliste_ins_netz_mit_preis(ctx):
    c, gesendet = ctx
    _figur(c, menge=3)
    lid = _liste(c)
    _artikel(c, lid, menge=2, erloes=15.0)           # 15 € für zwei → 7,50 je Stück
    _artikel(c, lid, nr="sw0099", menge=1)            # nicht in der Sammlung
    r = c.post(f"/api/lists/{lid}/netz", json={"an": True}).json()
    assert r["angeboten"] == 1 and r["fehlt"] == ["Figur sw0099"]
    z = _zeile()
    assert (z["shared"], z["share_qty"], z["share_deal"], z["share_price"]) == (1, 2, "verkauf", 7.5)
    o = gesendet[-1][0]
    assert (o["item_id"], o["qty"], o["deal"], o["price"], o["currency"]) == \
        ("sw0001", 2, "verkauf", 7.5, "EUR")


def test_ohne_preis_gilt_der_marktwert(ctx):
    c, gesendet = ctx
    _figur(c)
    lid = _liste(c)
    _artikel(c, lid, menge=1)
    c.post(f"/api/lists/{lid}/netz", json={"an": True})
    assert _zeile()["share_price"] == 5.0


def test_schon_zum_tausch_angeboten_wird_beides(ctx):
    c, _ = ctx
    _figur(c)
    with core.db() as conn:
        conn.execute("UPDATE collection SET shared = 1, share_deal = 'tausch'")
    lid = _liste(c)
    _artikel(c, lid, menge=1)
    c.post(f"/api/lists/{lid}/netz", json={"an": True})
    assert _zeile()["share_deal"] == "beides"
    # Herausnehmen: zurück auf Tausch? Nein – ganz heraus, aber die Art
    # fällt nicht auf „beides“ zurück, falls man es wieder teilt.
    c.post(f"/api/lists/{lid}/netz", json={"an": False})
    z = _zeile()
    assert z["shared"] == 0 and z["share_price"] is None and z["share_deal"] == "tausch"


def test_nur_verkaufslisten(ctx):
    c, _ = ctx
    lid = _liste(c, art="einkauf")
    assert c.post(f"/api/lists/{lid}/netz", json={"an": True}).status_code == 400


def test_auf_der_liste_verkauft_zieht_das_angebot_zurueck(ctx, monkeypatch):
    c, _ = ctx
    nachgezogen = []
    monkeypatch.setattr(community, "angebote_nachziehen_im_hintergrund",
                        lambda: nachgezogen.append(1))
    _figur(c, menge=3)
    lid = _liste(c)
    iid = _artikel(c, lid, menge=2)
    c.post(f"/api/lists/{lid}/netz", json={"an": True})
    # Einer geht auf dem Flohmarkt weg – die Liste hat aber zwei; hier
    # werden beide verkauft, und das Angebot (2) ist danach leer.
    assert c.post(f"/api/lists/items/{iid}/receive", json={"condition": "used"}).status_code == 200
    z = _zeile()
    assert z["quantity"] == 1 and z["shared"] == 0 and z["share_price"] is None
    assert nachgezogen == [1]


def test_uebers_netz_verkauft_hakt_die_liste_ab(ctx):
    """Austragen nach einem Netz-Verkauf hakt die Verkaufsliste ab – und
    fasst die Sammlung kein zweites Mal an."""
    c, _ = ctx
    _figur(c, menge=3)
    lid = _liste(c)
    iid = _artikel(c, lid, menge=2)
    c.post(f"/api/lists/{lid}/netz", json={"an": True})
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO trades (id, direction, other_id, other_name, item_id,"
            " item_name, status, created_at, updated_at, item_type, img_url,"
            " bricklink_url, condition, shipped_at, arrived_at) VALUES "
            "('trd_1', 'in', 'm_bruno', 'Bruno', 'sw0001', 'Figur', 'accepted', ?, ?,"
            " 'minifig', '', '', 'used', ?, ?)", (now, now, now, now))
    r = c.post("/api/hub/trades/trd_1/give", json={"quantity": 2, "condition": "used"})
    assert r.status_code == 200, r.text
    assert r.json()["liste_abgehakt"] == ["Verkauf"]
    assert _zeile()["quantity"] == 1                  # nur einmal abgezogen
    with core.db() as conn:
        it = conn.execute("SELECT * FROM shopping_items WHERE id = ?", (iid,)).fetchone()
        assert it["done"] == 1 and it["recv_mode"] == "netz" and it["im_netz"] == 0
    # Rückgängig geht hier nicht – das hat der Tausch geregelt.
    u = c.post(f"/api/lists/items/{iid}/undo")
    assert u.status_code == 409 and "Tausch-Netzwerk" in u.text


def test_teilverkauf_uebers_netz_senkt_die_menge(ctx):
    c, _ = ctx
    _figur(c, menge=3)
    lid = _liste(c)
    iid = _artikel(c, lid, menge=2)
    c.post(f"/api/lists/{lid}/netz", json={"an": True})
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO trades (id, direction, other_id, other_name, item_id,"
            " item_name, status, created_at, updated_at, item_type, img_url,"
            " bricklink_url, condition, shipped_at, arrived_at) VALUES "
            "('trd_2', 'in', 'm_bruno', 'Bruno', 'sw0001', 'Figur', 'accepted', ?, ?,"
            " 'minifig', '', '', 'used', ?, ?)", (now, now, now, now))
    c.post("/api/hub/trades/trd_2/give", json={"quantity": 1, "condition": "used"})
    with core.db() as conn:
        it = conn.execute("SELECT * FROM shopping_items WHERE id = ?", (iid,)).fetchone()
    assert it["done"] == 0 and it["qty"] == 1 and it["im_netz"] == 1
