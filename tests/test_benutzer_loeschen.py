"""Einen Benutzer löschen, der schon etwas hinterlassen hat.

Beim Löschen wurde bisher nur `collection.added_by` freigeräumt. Auf
`users(id)` zeigen aber noch vier weitere Spalten – und weil die Datenbank
mit `PRAGMA foreign_keys = ON` läuft, endete jeder Benutzer, der einen
Wunsch, eine Liste, einen Haken oder eine Push-Anmeldung hinterlassen
hatte, im Fehler 500.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _mkuser(name, admin=False):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, 'x', ?, 0, ?)",
            (name, int(admin), now))
        return cur.lastrowid


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "del.db"))
    core.init_db()
    aid = _mkuser("sven", admin=True)
    pid = _mkuser("paul")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(aid, "sven", True)
    return {"c": c, "aid": aid, "pid": pid}


def _existiert(uid):
    with core.db() as conn:
        return conn.execute("SELECT 1 FROM users WHERE id = ?",
                            (uid,)).fetchone() is not None


def test_ohne_spuren(ctx):
    r = ctx["c"].delete(f"/api/users/{ctx['pid']}")
    assert r.status_code == 200
    assert not _existiert(ctx["pid"])


def test_mit_sammlungseintrag(ctx):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " added_by, added_at) VALUES ('75192', 'set', 'Falcon', 1, ?, ?)",
            (ctx["pid"], now))
    assert ctx["c"].delete(f"/api/users/{ctx['pid']}").status_code == 200
    with core.db() as conn:
        # Das Stück bleibt in der Sammlung, nur ohne Einsteller.
        row = conn.execute("SELECT added_by FROM collection").fetchone()
    assert row["added_by"] is None


def test_mit_wunsch(ctx):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, added_by, added_at)"
            " VALUES ('75192', 'set', 'Falcon', ?, ?)", (ctx["pid"], now))
    assert ctx["c"].delete(f"/api/users/{ctx['pid']}").status_code == 200
    with core.db() as conn:
        row = conn.execute("SELECT added_by FROM wanted").fetchone()
    assert row["added_by"] is None


def test_mit_eigener_liste(ctx):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO shopping_lists (name, created_by, created_at)"
            " VALUES ('Flohmarkt', ?, ?)", (ctx["pid"], now))
    assert ctx["c"].delete(f"/api/users/{ctx['pid']}").status_code == 200
    with core.db() as conn:
        row = conn.execute("SELECT name, created_by FROM shopping_lists"
                           ).fetchone()
    # Die Liste bleibt – sie gehört der Instanz, nicht der Person.
    assert row["name"] == "Flohmarkt"
    assert row["created_by"] is None


def test_mit_abgehaktem_listeneintrag(ctx):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO shopping_lists (name, created_at) VALUES ('L', ?)",
            (now,))
        lid = cur.lastrowid
        conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name,"
            " done, done_by, added_at) VALUES (?, '75192', 'set', 'F', 1, ?, ?)",
            (lid, ctx["pid"], now))
    assert ctx["c"].delete(f"/api/users/{ctx['pid']}").status_code == 200
    with core.db() as conn:
        row = conn.execute("SELECT done, done_by FROM shopping_items"
                           ).fetchone()
    # Abgehakt bleibt abgehakt, nur der Name dahinter fällt weg.
    assert row["done"] == 1
    assert row["done_by"] is None


def test_mit_push_anmeldung(ctx):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO push_subs (user_id, endpoint, p256dh, auth,"
            " created_at) VALUES (?, 'https://push/x', 'k', 'a', ?)",
            (ctx["pid"], now))
    assert ctx["c"].delete(f"/api/users/{ctx['pid']}").status_code == 200
    with core.db() as conn:
        # Anders als die Einträge oben: die Anmeldung gehört nur ihm und geht mit.
        assert conn.execute("SELECT COUNT(*) c FROM push_subs"
                            ).fetchone()["c"] == 0


def test_alles_gleichzeitig(ctx):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " added_by, added_at) VALUES ('1', 'set', 'A', 1, ?, ?)",
            (ctx["pid"], now))
        conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, added_by, added_at)"
            " VALUES ('2', 'set', 'B', ?, ?)", (ctx["pid"], now))
        cur = conn.execute(
            "INSERT INTO shopping_lists (name, created_by, created_at)"
            " VALUES ('L', ?, ?)", (ctx["pid"], now))
        conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name,"
            " done, done_by, added_at) VALUES (?, '3', 'set', 'C', 1, ?, ?)",
            (cur.lastrowid, ctx["pid"], now))
        conn.execute(
            "INSERT INTO push_subs (user_id, endpoint, p256dh, auth,"
            " created_at) VALUES (?, 'https://push/y', 'k', 'a', ?)",
            (ctx["pid"], now))
    assert ctx["c"].delete(f"/api/users/{ctx['pid']}").status_code == 200
    assert not _existiert(ctx["pid"])


def test_sich_selbst_geht_weiter_nicht(ctx):
    r = ctx["c"].delete(f"/api/users/{ctx['aid']}")
    assert r.status_code == 400
    assert _existiert(ctx["aid"])
