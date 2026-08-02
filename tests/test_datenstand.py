"""Der Datenstand – „hat sich etwas geändert?".

Damit merkt die offene Ansicht von selbst, wenn ein anderes Gerät oder ein
Werkzeug an der Schnittstelle etwas angelegt hat. Abgefragt wird das alle
paar Sekunden, deshalb muss es billig sein – und es muss **jede** Änderung
zeigen, sonst bleibt die Ansicht stehen und niemand merkt es.
"""
import re
import time
from pathlib import Path

import pytest

import core
import main
from fastapi.testclient import TestClient

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "stand.db"))
    core.init_db()
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (int(time.time()),))
        uid = cur.lastrowid
        conn.execute("INSERT INTO shopping_lists (name, created_at)"
                     " VALUES ('Flohmarkt', ?)", (int(time.time()),))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def stand(client) -> dict:
    return client.get("/api/stand").json()


def test_ohne_anmeldung_nichts(client):
    roh = TestClient(main.app)
    assert roh.get("/api/stand").status_code in (401, 403)


def test_gleich_bleibt_gleich(client):
    """Sonst lüde die Ansicht im Takt neu, ohne dass etwas passiert wäre."""
    assert stand(client) == stand(client) == stand(client)


def test_neuer_sammlungseintrag_faellt_auf(client):
    vorher = stand(client)
    client.post("/api/collection", json={
        "item_id": "sw0402", "item_type": "minifig", "name": "Jabba",
        "condition": "used"})
    assert stand(client)["collection"] != vorher["collection"]


def test_geaenderte_menge_faellt_auf(client):
    """Zählen allein genügt nicht – die Zeile bleibt ja dieselbe."""
    client.post("/api/collection", json={
        "item_id": "sw0402", "item_type": "minifig", "name": "Jabba",
        "condition": "used"})
    vorher = stand(client)
    client.post("/api/collection", json={
        "item_id": "sw0402", "item_type": "minifig", "name": "Jabba",
        "condition": "used"})                    # Menge auf 2
    assert stand(client)["collection"] != vorher["collection"]


def test_neuer_listeneintrag_faellt_auf(client):
    vorher = stand(client)
    liste = client.get("/api/lists").json()["lists"][0]
    client.post(f"/api/lists/{liste['id']}/items", json={
        "item_id": "sw0397", "item_type": "minifig", "name": "Kithaba",
        "condition": "new", "paid_price": 7.0})
    assert stand(client)["lists"] != vorher["lists"]


def test_geaenderter_preis_faellt_auf(client):
    liste = client.get("/api/lists").json()["lists"][0]
    client.post(f"/api/lists/{liste['id']}/items", json={
        "item_id": "sw0397", "item_type": "minifig", "name": "Kithaba",
        "condition": "new", "paid_price": 7.0})
    with core.db() as conn:
        eintrag = conn.execute("SELECT id FROM shopping_items").fetchone()["id"]
    vorher = stand(client)
    client.patch(f"/api/lists/items/{eintrag}", json={"paid_price": 9.5})
    assert stand(client)["lists"] != vorher["lists"], (
        "eine Preisänderung muss auffallen")


def test_wunschliste_faellt_auf(client):
    vorher = stand(client)
    client.post("/api/wanted", json={
        "item_id": "sw0402", "item_type": "minifig", "name": "Jabba"})
    assert stand(client)["wanted"] != vorher["wanted"]


def test_sammlung_und_listen_sind_getrennt(client):
    """Sonst lüde die Sammlung neu, weil jemand eine Liste angefasst hat."""
    vorher = stand(client)
    liste = client.get("/api/lists").json()["lists"][0]
    client.post(f"/api/lists/{liste['id']}/items", json={
        "item_id": "sw0397", "item_type": "minifig", "name": "Kithaba",
        "condition": "used"})
    jetzt = stand(client)
    assert jetzt["lists"] != vorher["lists"]
    assert jetzt["collection"] == vorher["collection"]


# ---------------------------------------------------------------- Oberfläche

def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def test_die_oberflaeche_fragt_im_takt():
    quelle = js()
    assert "async function standPruefen(" in quelle
    takt = re.search(r"const STAND_TAKT = (\d+)", quelle)
    assert takt and 2000 <= int(takt.group(1)) <= 30000


def test_im_hintergrund_wird_nicht_gefragt():
    """Ein Tab im Hintergrund soll den Server nicht beschäftigen."""
    quelle = js()
    anfang = quelle.index("async function standPruefen(")
    assert "document.hidden" in quelle[anfang:anfang + 400]


def test_nur_bei_echter_aenderung_neu_laden():
    quelle = js()
    anfang = quelle.index("async function standPruefen(")
    koerper = quelle[anfang:quelle.index("\n}\n", anfang)]
    assert "vorher !== wert" in koerper
    assert "ansichtAuffrischen()" in koerper


def test_im_scan_tab_wird_nicht_aufgefrischt():
    """Dort steht ein Foto samt Treffern."""
    quelle = js()
    anfang = quelle.index("async function standPruefen(")
    koerper = quelle[anfang:quelle.index("\n}\n", anfang)]
    assert '["collection", "lists", "stats"]' in koerper
