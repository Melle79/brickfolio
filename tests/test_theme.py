"""Tests für das Design pro Benutzer und den Instanz-Standard."""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _user(name, admin):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, ?, ?, 0, ?)",
            (name, core.hash_password("pw1234"), int(admin), now))
        return cur.lastrowid


def _client(uid, name, admin):
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, name, admin)
    return c


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "th.db"))
    core.init_db()
    aid = _user("sven", True)
    kid = _user("paul", False)
    return {"admin": _client(aid, "sven", True),
            "kid": _client(kid, "paul", False)}


def test_default_is_classic(ctx):
    me = ctx["kid"].get("/api/me").json()
    assert me["theme"] is None and me["default_theme"] == "classic"


def test_user_theme_is_saved_and_returned(ctx):
    assert ctx["kid"].post("/api/me/theme",
                           json={"theme": "nova"}).status_code == 200
    assert ctx["kid"].get("/api/me").json()["theme"] == "nova"


def test_login_returns_saved_theme(ctx):
    ctx["kid"].post("/api/me/theme", json={"theme": "galaxy"})
    res = TestClient(main.app).post(
        "/api/login", json={"username": "paul", "password": "pw1234"}).json()
    assert res["theme"] == "galaxy"


def test_unknown_theme_refused(ctx):
    assert ctx["kid"].post("/api/me/theme",
                           json={"theme": "regenbogen"}).status_code == 400


def test_default_theme_is_admin_only(ctx):
    assert ctx["kid"].post("/api/settings/default_theme",
                           json={"theme": "nova"}).status_code == 403
    assert ctx["admin"].post("/api/settings/default_theme",
                             json={"theme": "nova"}).status_code == 200


def test_default_theme_applies_to_users_without_choice(ctx):
    ctx["admin"].post("/api/settings/default_theme", json={"theme": "galaxy"})
    # paul hat nichts gewählt -> theme None, default_theme galaxy
    me = ctx["kid"].get("/api/me").json()
    assert me["theme"] is None and me["default_theme"] == "galaxy"
    # ... und der Login-Screen kennt den Standard
    assert TestClient(main.app).get("/api/setup").json()["default_theme"] \
        == "galaxy"
