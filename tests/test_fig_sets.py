"""Tests für /api/fig_sets: alle Sets, in denen eine Figur vorkommt."""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "fs.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('finn', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "finn", True)
    return c


def test_returns_supersets(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(
        integrations, "bricklink_supersets",
        lambda no: [{"no": "75335-1", "name": "BD-1", "qty": 1},
                    {"no": "75399-1", "name": "E-Wing", "qty": 2}])
    sets = client.get("/api/fig_sets/sw1213").json()["sets"]
    assert [s["no"] for s in sets] == ["75335-1", "75399-1"]


def test_cached_second_call_hits_no_bricklink(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    calls = []

    def once(no):
        calls.append(no)
        return [{"no": "75335-1", "name": "BD-1", "qty": 1}]

    monkeypatch.setattr(integrations, "bricklink_supersets", once)
    client.get("/api/fig_sets/sw1213")
    client.get("/api/fig_sets/sw1213")
    assert len(calls) == 1          # zweiter Aufruf aus dem Cache


def test_empty_for_manual_or_rebrickable_number(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    assert client.get("/api/fig_sets/manuell-7").json()["sets"] == []
    assert client.get("/api/fig_sets/fig-1234").json()["sets"] == []


def test_empty_without_bricklink(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: False)
    assert client.get("/api/fig_sets/sw1213").json()["sets"] == []


def test_errors_are_swallowed(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)

    def boom(no):
        raise RuntimeError("BrickLink nicht erreichbar")

    monkeypatch.setattr(integrations, "bricklink_supersets", boom)
    r = client.get("/api/fig_sets/sw1213")
    assert r.status_code == 200 and r.json()["sets"] == []
