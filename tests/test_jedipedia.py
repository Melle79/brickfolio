"""Der optionale Verweis ins deutsche Star-Wars-Wiki.

Drei Dinge sind dabei leicht falsch gemacht:

- Direkt zu verlinken statt zu suchen. Der Katalog ist englisch, die
  Jedipedia deutsch: „Battle Droid" heißt dort „Kampfdroide", und
  `/wiki/Battle_Droid` wäre eine tote Adresse.
- Den Verweis überall zu zeigen. Das Wiki kennt nur Star Wars; bei einer
  City-Figur wäre er eine leere Trefferliste.
- Ihn ungefragt einzuschalten. Es ist ein Weg nach draußen aus einer App,
  die sonst vollständig im eigenen Netz läuft.
"""
import re
import time
from pathlib import Path

import pytest

import core
import main
from fastapi.testclient import TestClient

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def _fn(name):
    m = re.search(r"function %s\([^)]*\) \{.*?\n\}\n" % name,
                  APP_JS.read_text(), re.S)
    assert m, "%s nicht gefunden" % name
    return m.group(0)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "jp.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('sven', 'x', 1, ?)", (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_ausgeschaltet_voreingestellt(client):
    """Ein Weg nach draußen gehört nicht ungefragt in die App."""
    assert client.get("/api/config").json()["jedipedia"] is False


def test_der_schalter_haelt(client):
    client.post("/api/settings/jedipedia", json={"an": True})
    assert client.get("/api/config").json()["jedipedia"] is True
    client.post("/api/settings/jedipedia", json={"an": False})
    assert client.get("/api/config").json()["jedipedia"] is False


def test_der_verweis_sucht_statt_zu_raten():
    f = _fn("jedipediaLink")
    quelle = APP_JS.read_text()
    assert "Spezial:Suche?search=" in quelle
    # Kein direkter Artikelpfad – der wäre bei englischen Namen tot.
    assert "jedipedia.net/wiki/" not in f.replace(
        "JEDIPEDIA_SUCHE", "")


def test_nur_bei_star_wars():
    f = _fn("jedipediaLink")
    assert "istStarWars(" in f
    g = _fn("istStarWars")
    # `swtv` gehört dazu, `cty` nicht.
    assert "sw(tv)?" in g


def test_die_variante_faellt_weg():
    """„Boba Fett - Classic Grays" – gesucht wird die Figur, nicht ihre
    Bemalung."""
    f = _fn("jedipediaBegriff")
    assert '" - "' in f
    assert "replace" in f


def test_ohne_zustimmung_kein_verweis():
    f = _fn("jedipediaLink")
    assert "state.jedipedia" in f
    assert f.index("state.jedipedia") < f.index("return `")
