"""Dasselbe Set unter zwei Nummern.

Auf der Packung steht `21306`, BrickLink führt dasselbe Set als `21306-1`.
Wer eines von Hand erfasst und das andere scannt, hat zwei Zeilen für ein
Set – und die Sammlung zählt es doppelt. Die App erkennt das und fragt nach;
entscheiden muss der Mensch, denn ob wirklich zwei Kästen im Regal stehen,
weiß die Datenbank nicht.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "dub.db"))
    core.init_db()
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('sven', 'x', 1, 1, ?)",
                     (int(time.time()),))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def _erfassen(client, item_id, menge=1, preis=None, zustand="new"):
    """Eintrag anlegen, wie er **früher** entstanden ist.

    Seit 1.82.0 ergänzt die App beim Erfassen die BrickLink-Endung, ein
    Paar wie 21306/21306-1 kann also gar nicht mehr neu entstehen. Bestehende
    Sammlungen haben es trotzdem – deshalb hier direkt in die Datenbank,
    sonst prüfte der Test eine Lage, die es nicht mehr gibt.
    """
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " condition, added_at, added_by, paid_price, paid_source, paid_at)"
            " VALUES (?, 'set', 'The Beatles Yellow Submarine', ?, ?, ?, 1,"
            " ?, 'manual', ?)",
            (item_id, menge, zustand, now, preis, now if preis else None))
        if preis is not None:
            conn.execute(
                "INSERT INTO purchases (entry_id, quantity, unit_price,"
                " source, bought_at, note, created_at)"
                " VALUES (?, ?, ?, 'manual', ?, '', ?)",
                (cur.lastrowid, menge, round(preis / max(1, menge), 4), now, now))


def test_beim_erfassen_kommt_die_endung_dazu(client):
    """Vorbeugen statt aufräumen: Wer die Zahl von der Packung tippt, soll
    trotzdem in derselben Zeile landen wie ein gescanntes Exemplar."""
    r = client.post("/api/collection", json={
        "item_id": "21306", "item_type": "set", "name": "Yellow Submarine",
        "quantity": 1, "condition": "new"})
    assert r.status_code == 200
    items = client.get("/api/collection").json()["items"]
    assert [i["item_id"] for i in items] == ["21306-1"]


def test_zweites_erfassen_landet_in_derselben_zeile(client):
    client.post("/api/collection", json={
        "item_id": "21306-1", "item_type": "set", "name": "Yellow Submarine",
        "quantity": 1, "condition": "new"})
    r = client.post("/api/collection", json={
        "item_id": "21306", "item_type": "set", "name": "Gelbes U-Boot",
        "quantity": 1, "condition": "new"})
    assert r.json()["merged"] is True
    items = client.get("/api/collection").json()["items"]
    assert len(items) == 1 and items[0]["quantity"] == 2


@pytest.mark.parametrize("nummer,typ", [
    ("sw0312", "minifig"),          # Figurennummern bleiben, wie sie sind
    ("3001", "part"),               # Teile ebenso
    ("21306-2", "set"),             # schon eine Endung dran
    ("manuell-001", "set"),         # eigene Nummern nicht anfassen
])
def test_endung_nur_wo_sie_hingehoert(client, nummer, typ):
    client.post("/api/collection", json={
        "item_id": nummer, "item_type": typ, "name": "X",
        "quantity": 1, "condition": "used"})
    items = client.get("/api/collection").json()["items"]
    assert [i["item_id"] for i in items] == [nummer]


# ------------------------------------------------------------ Erkennung

@pytest.mark.parametrize("a,b", [
    ("21306", "21306-1"),
    ("75192", "75192-1"),
    ("10179", "10179-2"),
])
def test_nummernpaar_wird_erkannt(client, a, b):
    _erfassen(client, a)
    _erfassen(client, b)
    d = client.get("/api/notifications").json()["items"]
    dubletten = [n for n in d if n["kind"] == "dublette"]
    assert len(dubletten) == 1
    assert dubletten[0]["item_id"] == a          # die aufzugebende
    assert dubletten[0]["new_item_id"] == b      # die bleibende


@pytest.mark.parametrize("a,b", [
    ("sw0312", "sw0313"),        # zwei verschiedene Figuren
    ("fig-001234", "fig-001235"),
])
def test_verschiedene_artikel_bleiben_unbehelligt(client, a, b):
    for n in (a, b):
        client.post("/api/collection", json={
            "item_id": n, "item_type": "minifig", "name": n,
            "quantity": 1, "condition": "used"})
    d = client.get("/api/notifications").json()["items"]
    assert not [n for n in d if n["kind"] == "dublette"]


def test_zwei_echte_varianten_werden_nicht_angefasst(client):
    """`21306-1` und `21306-2` sind zwei Varianten desselben Sets – da weiß
    die App nicht, welche gemeint ist, und hält sich raus."""
    _erfassen(client, "21306-1")
    _erfassen(client, "21306-2")
    d = client.get("/api/notifications").json()["items"]
    assert not [n for n in d if n["kind"] == "dublette"]


# --------------------------------------------------------- Zusammenführen

def _hinweis(client):
    d = client.get("/api/notifications").json()["items"]
    return [n for n in d if n["kind"] == "dublette"][0]


def test_ein_exemplar_zweimal_erfasst(client):
    """Der häufige Fall: ein Kasten, zwei Zeilen. Danach steht dort eine
    Zeile mit Stückzahl 1."""
    _erfassen(client, "21306")
    _erfassen(client, "21306-1")
    n = _hinweis(client)
    r = client.post(f"/api/notifications/{n['id']}/merge", json={"modus": "ersetzen"})
    assert r.status_code == 200
    items = client.get("/api/collection").json()["items"]
    assert len(items) == 1
    assert items[0]["item_id"] == "21306-1"
    assert items[0]["quantity"] == 1


def test_wirklich_zwei_exemplare(client):
    _erfassen(client, "21306", menge=1)
    _erfassen(client, "21306-1", menge=2)
    n = _hinweis(client)
    r = client.post(f"/api/notifications/{n['id']}/merge", json={"modus": "zusammen"})
    assert r.status_code == 200
    items = client.get("/api/collection").json()["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 3


def test_kaufbuch_zieht_mit_um(client):
    """Beim Addieren gehören die Käufe der aufgegebenen Zeile dazu."""
    _erfassen(client, "21306", preis=189.75)
    _erfassen(client, "21306-1", preis=199.99)
    n = _hinweis(client)
    client.post(f"/api/notifications/{n['id']}/merge", json={"modus": "zusammen"})
    e = client.get("/api/collection").json()["items"][0]
    kaeufe = client.get(f"/api/collection/{e['id']}/purchases").json()["purchases"]
    assert len(kaeufe) == 2
    assert e["paid_price"] == pytest.approx(389.74)


def test_beim_ersetzen_bleibt_nur_ein_kauf(client):
    """Sonst stünde für einen Kasten der doppelte Betrag im Buch."""
    _erfassen(client, "21306", preis=189.75)
    _erfassen(client, "21306-1", preis=199.99)
    n = _hinweis(client)
    client.post(f"/api/notifications/{n['id']}/merge", json={"modus": "ersetzen"})
    e = client.get("/api/collection").json()["items"][0]
    kaeufe = client.get(f"/api/collection/{e['id']}/purchases").json()["purchases"]
    assert len(kaeufe) == 1
    assert e["paid_price"] == pytest.approx(199.99)


def test_hinweis_ist_danach_weg(client):
    _erfassen(client, "21306")
    _erfassen(client, "21306-1")
    n = _hinweis(client)
    client.post(f"/api/notifications/{n['id']}/merge", json={"modus": "ersetzen"})
    d = client.get("/api/notifications").json()["items"]
    assert not [x for x in d if x["kind"] == "dublette"]


def test_erfundener_modus_wird_abgelehnt(client):
    _erfassen(client, "21306")
    _erfassen(client, "21306-1")
    n = _hinweis(client)
    r = client.post(f"/api/notifications/{n['id']}/merge", json={"modus": "loeschen"})
    assert r.status_code == 422
