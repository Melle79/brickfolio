"""Tests für das Vergeben/Entziehen von Admin-Rechten.

Wichtigster Fall: Der letzte Admin darf sich nicht selbst (oder gegenseitig)
entrechten – sonst kümmert sich niemand mehr um die Instanz.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _mkuser(name, admin=False, dealer=False):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, 'x', ?, ?, ?)",
            (name, int(admin), int(dealer), now))
        return cur.lastrowid


def _client(uid, name, admin):
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, name, admin)
    return c


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "adm.db"))
    core.init_db()
    aid = _mkuser("sven", admin=True)
    pid = _mkuser("paul", admin=False)
    return {"admin": _client(aid, "sven", True), "aid": aid, "pid": pid,
            "paul": _client(pid, "paul", False)}


def _is_admin(uid):
    with core.db() as conn:
        return bool(conn.execute("SELECT is_admin FROM users WHERE id = ?",
                                 (uid,)).fetchone()["is_admin"])


def test_admin_can_promote_user(ctx):
    r = ctx["admin"].post(f"/api/users/{ctx['pid']}/admin",
                          json={"is_admin": True})
    assert r.status_code == 200
    assert _is_admin(ctx["pid"]) is True


def test_admin_can_demote_when_another_admin_exists(ctx):
    ctx["admin"].post(f"/api/users/{ctx['pid']}/admin", json={"is_admin": True})
    # Jetzt sind zwei Admins – einer darf wieder runter
    r = ctx["admin"].post(f"/api/users/{ctx['pid']}/admin",
                          json={"is_admin": False})
    assert r.status_code == 200
    assert _is_admin(ctx["pid"]) is False


def test_last_admin_cannot_be_demoted(ctx):
    # sven ist der einzige Admin
    r = ctx["admin"].post(f"/api/users/{ctx['aid']}/admin",
                          json={"is_admin": False})
    assert r.status_code == 400
    assert _is_admin(ctx["aid"]) is True


def test_non_admin_cannot_change_roles(ctx):
    r = ctx["paul"].post(f"/api/users/{ctx['aid']}/admin",
                         json={"is_admin": False})
    assert r.status_code == 403


def test_unknown_user_is_404(ctx):
    r = ctx["admin"].post("/api/users/99999/admin", json={"is_admin": True})
    assert r.status_code == 404
