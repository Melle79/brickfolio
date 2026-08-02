"""Name und Symbol der installierten App gehören der Instanz.

Legt man Brickfolio aufs Handy, steht dort der Name aus dem Manifest – und der
war bis 2.2.0 fest „Finn's Brickfolio", samt „FINN" im Symbol. Beides kommt
jetzt aus der Einstellung, die auch Titel und Logo speist.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "pwa.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    main._icon_cache.clear()
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_manifest_traegt_den_eingestellten_namen(client):
    client.post("/api/settings/owner_name", json={"name": "Sven"})
    m = client.get("/manifest.webmanifest").json()
    assert m["short_name"] == "Sven's Brickfolio"
    assert "Sven's Brickfolio" in m["name"]
    assert "Finn" not in m["name"]


def test_manifest_ohne_einstellung_bleibt_beim_standard(client):
    m = client.get("/manifest.webmanifest").json()
    assert m["short_name"].endswith("'s Brickfolio")


def test_titel_der_seite_traegt_den_namen(client):
    client.post("/api/settings/owner_name", json={"name": "Sven"})
    html = client.get("/").text
    assert "<title>Sven's Brickfolio</title>" in html
    assert "__OWNER__" not in html          # Platzhalter muss ersetzt sein


def test_symbol_wird_erzeugt_und_ist_ein_png(client):
    r = client.get("/icon/192.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_symbol_aendert_sich_mit_dem_namen(client):
    eins = client.get("/icon/512.png").content
    client.post("/api/settings/owner_name", json={"name": "Sven"})
    zwei = client.get("/icon/512.png").content
    assert eins != zwei, "Das Symbol muss den neuen Namen zeigen"


def test_nur_die_gebrauchten_groessen(client):
    for gr in (180, 192, 512):
        assert client.get(f"/icon/{gr}.png").status_code == 200
    assert client.get("/icon/999.png").status_code == 404


def test_symbol_kommt_beim_zweiten_mal_aus_dem_zwischenspeicher(client):
    client.get("/icon/192.png")
    vorher = len(main._icon_cache)
    client.get("/icon/192.png")
    assert len(main._icon_cache) == vorher
