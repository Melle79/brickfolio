"""Was der Gesamttest am 26.09.2026 fand.

Alle 181 Schnittstellen wurden gegen eine frische Instanz aufgerufen – gültig,
ohne Anmeldung, als Standard-Benutzer und mit kaputten Eingaben. Die Fälle
hier sind die, bei denen die App etwas anderes tat als versprochen.
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
        kind = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('kind', 'x', 0, 0, ?)", (now,)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(profi, "admin", True)
    k = TestClient(main.app)
    k.headers["Authorization"] = "Bearer " + core.create_token(kind, "kind", False)
    return c, k


def _figur(c, **mehr):
    daten = {"item_id": "sw0002", "item_type": "minifig", "name": "X",
             "quantity": 1, "condition": "used"}
    daten.update(mehr)
    r = c.post("/api/collection", json=daten)
    assert r.status_code == 200, r.text
    with core.db() as conn:
        return conn.execute("SELECT * FROM collection WHERE item_id = ?",
                            (daten["item_id"],)).fetchone()


def _posten(eid):
    with core.db() as conn:
        return [(r["quantity"], r["unit_price"]) for r in conn.execute(
            "SELECT quantity, unit_price FROM purchases WHERE entry_id = ? "
            "ORDER BY id", (eid,))]


# ------------------------------------------------ Unendlich ist kein Preis

@pytest.mark.parametrize("roh", ['1e999', '"Infinity"', '"-Infinity"'])
def test_unendlicher_preis_wird_abgelehnt(ctx, roh):
    """Angenommen und gespeichert, danach gaben Sammlung, Statistik und
    Sicherung für alle 500 – „Out of range float values are not JSON
    compliant“."""
    c, _ = ctx
    r = c.post("/api/collection", content=(
        '{"item_id":"inf0","name":"n","paid_price":%s}' % roh).encode(),
        headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert c.get("/api/collection").status_code == 200


def test_nan_gibt_422_statt_500(ctx):
    """Die Ablehnung wiederholte `input: nan` – und das ließ sich selbst
    nicht als JSON schreiben."""
    c, _ = ctx
    r = c.post("/api/collection", content=b'{"item_id":"x","name":"n",'
               b'"paid_price":NaN}', headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["msg"]


def test_eingabefehler_wiederholen_keine_passwoerter(ctx):
    c, _ = ctx
    r = c.post("/api/users", json={"username": "neu", "password": "kurz"})
    assert r.status_code == 422
    assert "kurz" not in r.text


@pytest.mark.parametrize("roh, wert", [
    ("12,50", 12.5), ("1.234,56", 1234.56), ("1,234.56", 1234.56),
    ("7.5", 7.5), ("0", 0.0)])
def test_csv_betrag_liest_beide_schreibweisen(roh, wert):
    assert main._csv_betrag(roh) == wert


@pytest.mark.parametrize("roh", ["inf", "nan", "1e999", "-3"])
def test_csv_betrag_ohne_unendlich_und_negativ(roh):
    assert main._csv_betrag(roh) is None


# ------------------------------------------------ Kaufpreise sind Profisache

def test_standard_benutzer_setzt_keinen_kaufpreis(ctx):
    c, kind = ctx
    e = _figur(c, paid_price=8.0, quantity=2)
    r = kind.patch(f"/api/collection/{e['id']}", json={"paid_price": 1.0})
    assert r.status_code == 403
    assert _posten(e["id"]) == [(2, 4.0)]


def test_standard_benutzer_legt_ohne_preis_an(ctx):
    _, kind = ctx
    e = _figur(kind, item_id="sw0003", paid_price=5.0)
    assert e["paid_price"] is None
    assert _posten(e["id"]) == []


def test_bildadresse_mit_javascript_wird_abgelehnt(ctx):
    c, _ = ctx
    e = _figur(c)
    r = c.patch(f"/api/collection/{e['id']}",
                json={"img_url": "javascript:alert(1)"})
    assert r.status_code == 422


# ------------------------------------------------ Menge und Kaufbuch

def test_weniger_stueck_heisst_weniger_bezahlt(ctx):
    """„3 → 1“ ließ die 8 € für drei Stück an der Zeile stehen."""
    c, _ = ctx
    e = _figur(c, quantity=3, paid_price=9.0)
    c.patch(f"/api/collection/{e['id']}", json={"quantity": 1})
    with core.db() as conn:
        z = conn.execute("SELECT quantity, paid_price FROM collection "
                         "WHERE id = ?", (e["id"],)).fetchone()
    assert (z["quantity"], z["paid_price"]) == (1, 3.0)


# ------------------------------------------------ Rückgängig in der Liste

def _liste_mit_artikel(c, qty=3, preis=None):
    lid = c.post("/api/lists", json={"name": "Flohmarkt"}).json()["id"]
    c.post(f"/api/lists/{lid}/items", json={
        "item_id": "sw0002", "item_type": "minifig", "name": "X",
        "qty": qty, "condition": "used", "paid_price": preis})
    with core.db() as conn:
        return conn.execute("SELECT id FROM shopping_items").fetchone()["id"]


def test_rueckgaengig_nimmt_neu_angelegte_zeile_wieder_weg(ctx):
    c, _ = ctx
    iid = _liste_mit_artikel(c, qty=2, preis=6.0)
    assert c.post(f"/api/lists/items/{iid}/receive",
                  json={"condition": "used"}).json()["ok"]
    r = c.post(f"/api/lists/items/{iid}/undo").json()
    assert r["reverted"] is True
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM collection").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0] == 0


def test_rueckgaengig_nach_dazubuchen_bucht_nicht_doppelt(ctx):
    """3 → 6 → Rückgängig → noch einmal annehmen ergab 9 Stück und zwei
    gleiche Kaufposten."""
    c, _ = ctx
    e = _figur(c, quantity=3)
    iid = _liste_mit_artikel(c, qty=3, preis=15.0)
    c.post(f"/api/lists/items/{iid}/receive",
           json={"condition": "used", "mode": "add"})
    assert c.post(f"/api/lists/items/{iid}/undo").json()["reverted"] is True
    c.post(f"/api/lists/items/{iid}/receive",
           json={"condition": "used", "mode": "add"})
    with core.db() as conn:
        z = conn.execute("SELECT quantity, paid_price FROM collection "
                         "WHERE id = ?", (e["id"],)).fetchone()
    assert (z["quantity"], z["paid_price"]) == (6, 15.0)
    assert _posten(e["id"]) == [(3, 5.0)]


def test_rueckgaengig_nach_ersetzen_bleibt_ehrlich(ctx):
    """Ersetzen hat die alte Menge verworfen – das lässt sich nicht umkehren."""
    c, _ = ctx
    _figur(c, quantity=3)
    iid = _liste_mit_artikel(c, qty=1)
    c.post(f"/api/lists/items/{iid}/receive",
           json={"condition": "used", "mode": "replace"})
    assert c.post(f"/api/lists/items/{iid}/undo").json()["reverted"] is False


# ------------------------------------------------ Kaufpreise lesen

def test_standard_benutzer_sieht_keine_kaufpreise(ctx):
    """Handbuch Kapitel 3: „Kaufpreise & Gewinn sehen“ nur Profis. Die
    Oberfläche blendete sie aus, die Schnittstelle lieferte sie trotzdem."""
    c, kind = ctx
    e = _figur(c, paid_price=8.0)
    zeile = kind.get("/api/collection").json()["items"][0]
    assert zeile["paid_price"] is None
    assert kind.get(f"/api/collection/{e['id']}/purchases").status_code == 403
    t = kind.get("/api/stats/dashboard").json()
    assert t["totals"]["paid"] is None and t["totals"]["profit"] is None
    assert t["winners"] == [] and t["losers"] == []
    # Der Profi sieht weiter alles.
    assert c.get("/api/collection").json()["items"][0]["paid_price"] == 8.0


def test_listenpreise_nur_fuer_profis(ctx):
    c, kind = ctx
    _liste_mit_artikel(c, qty=1, preis=4.0)
    liste = kind.get("/api/lists").json()["lists"][0]
    assert liste["items"][0]["paid_price"] is None
    assert liste["stats"]["paid_sum"] == 0
    assert c.get("/api/lists").json()["lists"][0]["stats"]["paid_sum"] == 4.0


def test_geleerter_kaufpreis_bleibt_leer(ctx):
    """`null` hieß bisher „nicht angegeben“ – nach dem Neuladen war der
    gelöschte Preis wieder da."""
    c, kind = ctx
    e = _figur(c, paid_price=12.5)
    assert kind.patch(f"/api/collection/{e['id']}",
                      json={"paid_price": None}).status_code == 403
    assert c.patch(f"/api/collection/{e['id']}",
                   json={"paid_price": None}).status_code == 200
    with core.db() as conn:
        z = conn.execute("SELECT paid_price FROM collection WHERE id = ?",
                         (e["id"],)).fetchone()
    assert z["paid_price"] is None and _posten(e["id"]) == []
    # Ein PATCH ohne das Feld lässt einen Preis dagegen stehen.
    c.patch(f"/api/collection/{e['id']}", json={"paid_price": 3.0})
    c.patch(f"/api/collection/{e['id']}", json={"notes": "x"})
    assert _posten(e["id"]) == [(1, 3.0)]
