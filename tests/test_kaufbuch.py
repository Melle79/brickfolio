"""Zwei gleiche Sets, zwei Preise.

Dasselbe Set einmal bei LEGO für 39,99 und einmal im Markt für 34,99: In der
Sammlung ist das **eine** Zeile mit Stückzahl 2, denn `item_id` + Typ +
Zustand sind eindeutig. Die Summe stimmte immer – aber welcher Kauf welcher
war, ließ sich danach nicht mehr sagen. Das Kaufbuch hält die Einzelposten,
`paid_price` bleibt ihre Summe.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient

SET = {"item_id": "75192-1", "item_type": "set", "name": "Millennium Falcon",
       "quantity": 1, "condition": "new"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "kauf.db"))
    core.init_db()
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('sven', 'x', 1, 1, ?)",
                     (int(time.time()),))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def _eintrag(client, **extra):
    client.post("/api/collection", json={**SET, **extra})
    return client.get("/api/collection").json()["items"][0]


# ------------------------------------------------------- Der Kernfall

def test_zwei_kaeufe_verschiedene_preise(client):
    e = _eintrag(client, paid_price=39.99, paid_source="manual")
    r = client.post(f"/api/collection/{e['id']}/purchases",
                    json={"quantity": 1, "price": 34.99, "source": "MediaMarkt"})
    assert r.status_code == 200
    assert r.json()["quantity"] == 2

    d = client.get(f"/api/collection/{e['id']}/purchases").json()["purchases"]
    assert len(d) == 2
    preise = sorted(p["unit_price"] for p in d)
    assert preise == [34.99, 39.99]
    assert {p["source"] for p in d} == {"manual", "MediaMarkt"}

    # Die Summe bleibt das, was Statistik und Gewinn benutzen
    eintrag = client.get("/api/collection").json()["items"][0]
    assert eintrag["quantity"] == 2
    assert eintrag["paid_price"] == pytest.approx(74.98)


def test_gilt_genauso_fuer_figuren(client):
    """Der Kauf hängt am Eintrag, nicht am Typ."""
    client.post("/api/collection", json={
        "item_id": "sw0312", "item_type": "minifig", "name": "TX-20",
        "quantity": 1, "condition": "used", "paid_price": 4.5})
    e = client.get("/api/collection").json()["items"][0]
    client.post(f"/api/collection/{e['id']}/purchases",
                json={"quantity": 2, "price": 7.0, "source": "Flohmarkt"})
    eintrag = client.get("/api/collection").json()["items"][0]
    assert eintrag["quantity"] == 3
    assert eintrag["paid_price"] == pytest.approx(11.5)
    d = client.get(f"/api/collection/{e['id']}/purchases").json()["purchases"]
    # 7,00 für zwei Stück heißt 3,50 je Stück
    assert sorted(p["unit_price"] for p in d) == [3.5, 4.5]


def test_kauf_zuruecknehmen(client):
    e = _eintrag(client, paid_price=39.99)
    client.post(f"/api/collection/{e['id']}/purchases",
                json={"quantity": 1, "price": 34.99, "source": "Markt"})
    kaeufe = client.get(f"/api/collection/{e['id']}/purchases").json()["purchases"]
    markt = [k for k in kaeufe if k["source"] == "Markt"][0]
    r = client.delete(f"/api/collection/{e['id']}/purchases/{markt['id']}")
    assert r.status_code == 200
    eintrag = client.get("/api/collection").json()["items"][0]
    assert eintrag["quantity"] == 1
    assert eintrag["paid_price"] == pytest.approx(39.99)


# ------------------------------------------- Summe und Buch bleiben gleich

def test_summe_stimmt_nach_jedem_weg(client):
    """`paid_price` wird an sechs Stellen geschrieben. Keine davon darf am
    Kaufbuch vorbeigehen, sonst zeigt die Karte eine andere Zahl als die
    Aufstellung darunter."""
    e = _eintrag(client, paid_price=39.99)

    # noch einmal dasselbe über „Zur Sammlung", diesmal mit Preis
    client.post("/api/collection", json={**SET, "paid_price": 34.99})
    # CSV-Import
    client.post("/api/import/csv", json={
        "csv": "Nummer,Typ,Name,Anzahl,Zustand,Bezahlt\n"
               "75192-1,Set,Millennium Falcon,1,Neu,29.99\n"})

    eintrag = client.get("/api/collection").json()["items"][0]
    kaeufe = client.get(f"/api/collection/{eintrag['id']}/purchases").json()["purchases"]
    summe = round(sum(k["quantity"] * k["unit_price"] for k in kaeufe), 2)
    assert eintrag["paid_price"] == pytest.approx(summe)
    assert eintrag["quantity"] == 3
    assert summe == pytest.approx(104.97)


def test_von_hand_gesetzter_preis_setzt_das_buch_zurueck(client):
    """Wer den Kaufpreis der Zeile überschreibt, meint den ganzen Betrag –
    dann darf darunter keine Aufstellung stehen, die etwas anderes ergibt."""
    e = _eintrag(client, paid_price=39.99)
    client.post(f"/api/collection/{e['id']}/purchases",
                json={"quantity": 1, "price": 34.99})
    client.patch(f"/api/collection/{e['id']}", json={"paid_price": 50.0})
    eintrag = client.get("/api/collection").json()["items"][0]
    kaeufe = client.get(f"/api/collection/{e['id']}/purchases").json()["purchases"]
    assert eintrag["paid_price"] == pytest.approx(50.0)
    assert len(kaeufe) == 1
    summe = round(sum(k["quantity"] * k["unit_price"] for k in kaeufe), 2)
    assert summe == pytest.approx(50.0)


def test_zustandswechsel_nimmt_das_buch_mit(client):
    """Wird „neu" zu „gebraucht" und gibt es dort schon eine Zeile, werden
    beide zusammengeführt – die Einzelposten dürfen dabei nicht verfallen."""
    client.post("/api/collection", json={**SET, "condition": "used",
                                         "paid_price": 20.0})
    client.post("/api/collection", json={**SET, "paid_price": 39.99})
    neu = [i for i in client.get("/api/collection").json()["items"]
           if i["condition"] == "new"][0]
    client.patch(f"/api/collection/{neu['id']}", json={"condition": "used"})

    items = client.get("/api/collection").json()["items"]
    assert len(items) == 1
    ziel = items[0]
    kaeufe = client.get(f"/api/collection/{ziel['id']}/purchases").json()["purchases"]
    assert len(kaeufe) == 2
    assert ziel["paid_price"] == pytest.approx(59.99)


def test_geloeschter_eintrag_laesst_kein_buch_zurueck(client):
    e = _eintrag(client, paid_price=39.99)
    client.delete(f"/api/collection/{e['id']}")
    with core.db() as conn:
        rest = conn.execute("SELECT COUNT(*) AS n FROM purchases").fetchone()
    assert rest["n"] == 0


def test_bestand_wird_uebernommen(tmp_path, monkeypatch):
    """Wer schon Kaufpreise erfasst hat, soll sie im Buch wiederfinden –
    sonst stünde bei allem Bisherigen eine leere Aufstellung."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "alt.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " created_at) VALUES ('sven', 'x', 1, ?)", (now,))
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " condition, added_at, paid_price, paid_source, paid_at) VALUES"
            " ('10179-1', 'set', 'UCS', 2, 'used', ?, 120.0, 'manual', ?)",
            (now, now))
        conn.execute("DELETE FROM purchases")     # Ausgangslage: nichts da
    core.init_db()                                # Migration erneut
    with core.db() as conn:
        k = conn.execute("SELECT quantity, unit_price FROM purchases").fetchall()
    assert len(k) == 1
    assert k[0]["quantity"] == 2 and k[0]["unit_price"] == pytest.approx(60.0)
