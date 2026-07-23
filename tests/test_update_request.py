"""Tests für das Anfordern eines Updates aus der App heraus.

Die App führt das Update nicht selbst aus – sie legt nur eine Markierung im
Datenverzeichnis ab, die der Helfer auf dem Server aufgreift.
"""
import json
import os
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _mk_user(is_admin):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer, "
            "created_at) VALUES (?, 'x', ?, 1, ?)",
            ("admin" if is_admin else "kind", int(is_admin), now))
        return cur.lastrowid


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "up.db"))
    core.init_db()
    admin_id = _mk_user(True)
    kid_id = _mk_user(False)
    admin = TestClient(main.app)
    admin.headers["Authorization"] = (
        "Bearer " + core.create_token(admin_id, "admin", True))
    kid = TestClient(main.app)
    kid.headers["Authorization"] = (
        "Bearer " + core.create_token(kid_id, "kind", False))
    alive = tmp_path / "update-watch-alive"
    alive.write_text("")            # Helfer läuft (frisches Lebenszeichen)
    return {"admin": admin, "kid": kid,
            "flag": str(tmp_path / "update-requested.json"),
            "alive": alive}


def test_no_update_pending_by_default(ctx):
    body = ctx["kid"].get("/api/update/status").json()
    assert body["pending"] is False
    assert body["version"] == core.APP_VERSION


def test_admin_can_request_and_flag_is_written(ctx):
    r = ctx["admin"].post("/api/update/request", json={"delay": 60})
    assert r.status_code == 200
    assert os.path.exists(ctx["flag"])
    with open(ctx["flag"]) as f:
        flag = json.load(f)
    # Karenzzeit steckt in der Datei, damit sie auch ohne Browser gilt
    assert flag["execute_after"] - flag["requested_at"] == 60
    assert flag["by"] == "admin"


def test_status_is_visible_to_every_user(ctx):
    ctx["admin"].post("/api/update/request", json={"delay": 300})
    body = ctx["kid"].get("/api/update/status").json()
    assert body["pending"] is True
    assert 290 <= body["seconds_left"] <= 300
    assert body["by"] == "admin"


def test_immediate_request_has_no_wait(ctx):
    ctx["admin"].post("/api/update/request", json={"delay": 0})
    assert ctx["kid"].get("/api/update/status").json()["seconds_left"] == 0


def test_non_admin_cannot_request(ctx):
    assert ctx["kid"].post("/api/update/request",
                           json={"delay": 60}).status_code == 403
    assert not os.path.exists(ctx["flag"])


def test_non_admin_cannot_cancel(ctx):
    ctx["admin"].post("/api/update/request", json={"delay": 60})
    assert ctx["kid"].post("/api/update/cancel").status_code == 403
    assert os.path.exists(ctx["flag"])


def test_admin_can_cancel(ctx):
    ctx["admin"].post("/api/update/request", json={"delay": 60})
    assert ctx["admin"].post("/api/update/cancel").status_code == 200
    assert not os.path.exists(ctx["flag"])
    assert ctx["kid"].get("/api/update/status").json()["pending"] is False


def test_cancel_without_request_is_harmless(ctx):
    assert ctx["admin"].post("/api/update/cancel").status_code == 200


def test_delay_is_bounded(ctx):
    assert ctx["admin"].post("/api/update/request",
                             json={"delay": -1}).status_code == 422
    assert ctx["admin"].post("/api/update/request",
                             json={"delay": 99999}).status_code == 422


def test_broken_flag_does_not_break_status(ctx):
    with open(ctx["flag"], "w") as f:
        f.write("kein json")
    assert ctx["kid"].get("/api/update/status").json()["pending"] is False


# --------------------------------------------- Helfer auf dem Server
# Ohne ihn passiert nichts – die App darf dann gar nicht erst anbieten,
# ein Update auszulösen, sonst wartet sie ewig.

def test_status_reports_running_helper(ctx):
    assert ctx["kid"].get("/api/update/status").json()["helper_active"] is True


def test_status_reports_missing_helper(ctx):
    ctx["alive"].unlink()
    body = ctx["kid"].get("/api/update/status").json()
    assert body["helper_active"] is False
    assert body["helper_seen_at"] is None


def test_status_reports_stale_helper(ctx):
    old = time.time() - 3600            # letztes Lebenszeichen vor einer Stunde
    os.utime(ctx["alive"], (old, old))
    assert ctx["kid"].get("/api/update/status").json()["helper_active"] is False


def test_request_refused_without_helper(ctx):
    ctx["alive"].unlink()
    r = ctx["admin"].post("/api/update/request", json={"delay": 60})
    assert r.status_code == 409
    assert "Helfer" in r.json()["detail"]
    assert not os.path.exists(ctx["flag"])      # nichts angefordert
