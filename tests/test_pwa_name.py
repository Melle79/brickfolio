"""Name und Symbol der installierten App gehören der Instanz.

Legt man Brickfolio aufs Handy, steht dort der Name aus dem Manifest – und der
war bis 2.2.0 ein fest eingebauter Vorname, auch im Symbol. Beides kommt
jetzt aus der Einstellung, die auch Titel und Logo speist.

Das Symbol im Browser-Reiter blieb dabei bis 2.79.2 zurück: `/favicon.ico`
reichte eine feste Datei durch. Seit 2.80.0 kommt auch sie aus dem Erzeuger.
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
            " created_at) VALUES ('anna', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    main._icon_cache.clear()
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    return c


def test_manifest_traegt_den_eingestellten_namen(client):
    client.post("/api/settings/owner_name", json={"name": "Anna"})
    m = client.get("/manifest.webmanifest").json()
    assert m["short_name"] == "Anna's Brickfolio"
    assert "Anna's Brickfolio" in m["name"]
    assert "Carla" not in m["name"]


def test_manifest_ohne_einstellung_heisst_dein_brickfolio(client):
    """Ohne gesetzten Namen gehört die Instanz niemandem Bestimmten.

    Früher stand hier ein fester Vorname – den trug dann jede fremde
    Installation, die nichts eingestellt hatte, bis aufs Handy.
    """
    m = client.get("/manifest.webmanifest").json()
    assert m["short_name"] == "Dein Brickfolio"
    assert "'s" not in m["short_name"]


def test_titel_der_seite_traegt_den_namen(client):
    client.post("/api/settings/owner_name", json={"name": "Anna"})
    html = client.get("/").text
    assert "<title>Anna's Brickfolio</title>" in html
    assert "__OWNER__" not in html          # Platzhalter muss ersetzt sein


def test_symbol_wird_erzeugt_und_ist_ein_png(client):
    r = client.get("/icon/192.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_symbol_aendert_sich_mit_dem_namen(client):
    eins = client.get("/icon/512.png").content
    client.post("/api/settings/owner_name", json={"name": "Anna"})
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


# ── Das Reiter-Symbol ──────────────────────────────────────────────────
# Es kam bis 2.79.2 als feste Datei aus dem Repo – mit einem festen Vornamen darin, auf
# jeder fremden Instanz. Die Proben hier halten fest, dass es erzeugt wird.

def test_favicon_ist_ein_ico(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/x-icon"
    assert r.content[:4] == b"\x00\x00\x01\x00", "kein ICO-Behälter"


def test_favicon_aendert_sich_mit_dem_namen(client):
    eins = client.get("/favicon.ico").content
    client.post("/api/settings/owner_name", json={"name": "Anna"})
    zwei = client.get("/favicon.ico").content
    assert eins != zwei, "Das Reiter-Symbol muss den neuen Namen zeigen"


def test_favicon_ist_nicht_die_mitgelieferte_datei(client):
    """Der Rückfall darf nicht die Regel sein.

    Genau das war der Fehler: Die Route reichte die Datei durch, und
    niemandem fiel es auf, weil sie auf der ursprünglichen Instanz richtig aussah.
    """
    import os
    mitgeliefert = open(os.path.join(
        main.FRONTEND_DIR, "icons", "favicon.ico"), "rb").read()
    assert client.get("/favicon.ico").content != mitgeliefert


def test_titel_ohne_namen_ist_nicht_s_brickfolio(client):
    """Der Reiter darf nicht »'s Brickfolio« heißen.

    Bis 2.84.1 stand in der Vorlage `__OWNER__'s Brickfolio`, und der Server
    ersetzte nur den nackten Namen. Ohne gesetzten Namen klebte das
    Genitiv-s damit an einer leeren Zeichenkette – auf **jeder** frischen
    Installation, bevor jemand einen Namen eintrug. Das Manifest hatte den
    Fall längst richtig, die Seite nicht.
    """
    html = client.get("/").text
    assert "<title>Dein Brickfolio</title>" in html
    assert "'s Brickfolio</title>" not in html
    assert "__APPTITLE__" not in html


def test_logo_traegt_ohne_namen_keinen_fremden_namen(client):
    """Das Logo kam mit einem festen Vornamen aus der Vorlage und blieb ohne Namen stehen.

    `applyOwnerName` stieg bei leerem Namen sofort aus, also überschrieb
    nichts den Platzhalter – im Willkommensbogen einer fremden Installation
    stand damit ein fremder Vorname.
    """
    html = client.get("/").text
    assert '<span class="logo-name"></span>' in html
    assert "__OWNERUP__" not in html


def test_logo_traegt_den_namen_in_grossbuchstaben(client):
    client.post("/api/settings/owner_name", json={"name": "Anna"})
    html = client.get("/").text
    assert '<span class="logo-name">ANNA</span>' in html
