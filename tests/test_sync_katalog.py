"""Katalog für externen Zugriff (`/api/sync/katalog`).

Entstanden aus der Frage, wie ein externer Zugriff mit eigener Datenbank
weiter nachschlagen kann, wenn die Instanz nicht erreichbar ist – ohne die
BrickLink-Schlüssel der Instanz zu bekommen. Der öffentliche Abzug hat keine
Namen; die trägt jede Instanz über ihren eigenen Zugang nach. Also holt der
externe Zugriff den Katalog samt Namen von hier.
"""
import time

import pytest
from fastapi.testclient import TestClient

import core
import main
import sync


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "katalog.db"))
    core.init_db()
    with core.db() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash, is_admin, "
                     "is_dealer, created_at) VALUES (1, 'standard', 'x', 0, 0, ?)",
                     (int(time.time()),))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "standard", False)
    return c


def _figur(conn, nr, zeit, name="", typ="minifig"):
    conn.execute("INSERT OR REPLACE INTO katalog_index (item_no, item_type, name, "
                 "such, img_url, merkmale, updated_at) VALUES (?, ?, ?, '', '', "
                 "'torso red', ?)", (nr, typ, name, zeit))


def test_namen_kommen_mit_und_ohne_anmeldung_nichts(client):
    with core.db() as conn:
        _figur(conn, "sw0001a", 100, "Battle Droid")
    d = client.get("/api/sync/katalog").json()
    assert [(e["item_no"], e["name"]) for e in d["eintraege"]] == [("sw0001a", "Battle Droid")]
    assert d["stand"] == 100 and d["mehr"] is False
    assert TestClient(main.app).get("/api/sync/katalog").status_code == 401


def test_blaettern_innerhalb_derselben_zeit(client, monkeypatch):
    """Ein ganzer Abzug trägt dieselbe Zeit. Mit `seit` allein käme nach der
    ersten Seite nichts mehr – deshalb `nach`."""
    with core.db() as conn:
        for i in range(5):
            _figur(conn, f"sw000{i}", 100)
    gesehen, nach = [], ""
    while True:
        d = client.get("/api/sync/katalog", params={"limit": 2, "nach": nach}).json()
        gesehen += [e["item_no"] for e in d["eintraege"]]
        if not d["mehr"]:
            break
        nach = d["weiter"]
    assert gesehen == [f"sw000{i}" for i in range(5)]


def test_nur_was_sich_geaendert_hat(client):
    with core.db() as conn:
        _figur(conn, "sw0001", 100)
        _figur(conn, "sw0002", 200, "Boba Fett")
    d = client.get("/api/sync/katalog", params={"seit": 150}).json()
    assert [e["item_no"] for e in d["eintraege"]] == ["sw0002"]
    # Dieselbe Sekunde noch einmal – was darin nach dem Abruf dazukam,
    # fehlte sonst für immer.
    assert [e["item_no"] for e in client.get("/api/sync/katalog", params={"seit": 200}).json()["eintraege"]] == ["sw0002"]
    assert client.get("/api/sync/katalog", params={"seit": 201}).json()["eintraege"] == []


def test_setinhalte_nummern_und_kategorien_auf_der_ersten_seite(client):
    with core.db() as conn:
        _figur(conn, "sw0001", 100)
        _figur(conn, "sw0002", 100)
        conn.execute("INSERT INTO set_contents (set_no, fig_no, qty) VALUES ('75192-1', 'sw0001', 2)")
        conn.execute("INSERT INTO set_meta (set_no, figs_fetched_at) VALUES ('75192-1', 300)")
        conn.execute("INSERT INTO bl_nummern (item_id, bl_no, checked_at) VALUES ('2586pr0028', '2586ps1', 300)")
        conn.execute("INSERT INTO katalog_kategorien (id, name, parent_id, geholt_at) VALUES ('65', 'Star Wars', '', 1)")
    erste = client.get("/api/sync/katalog", params={"limit": 1}).json()
    assert erste["setinhalte"] == [{"set_no": "75192-1", "fig_no": "sw0001", "qty": 2}]
    assert erste["bl_nummern"] == [{"item_id": "2586pr0028", "bl_no": "2586ps1"}]
    assert erste["kategorien"][0]["name"] == "Star Wars"
    zweite = client.get("/api/sync/katalog", params={"limit": 1, "nach": erste["weiter"]}).json()
    assert "setinhalte" not in zweite
    # Später geholt heißt: beim nächsten Mal nicht noch einmal.
    assert client.get("/api/sync/katalog", params={"seit": 301}).json()["setinhalte"] == []


def test_kommt_gepackt(client):
    with core.db() as conn:
        for i in range(200):
            _figur(conn, f"sw{i:04d}", 100, "Clone Trooper")
    r = client.get("/api/sync/katalog", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


def test_kaputtes_nach(client):
    assert client.get("/api/sync/katalog", params={"nach": "x"}).status_code == 400
