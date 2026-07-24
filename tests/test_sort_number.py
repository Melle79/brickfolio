"""Sortierung der Sammlung nach BrickLink-Nummer."""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "sort.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " created_at) VALUES ('a', 'x', 1, ?)", (now,))
        for iid, name in [("sw0100", "Zebra"), ("75335-1", "Alpha"),
                          ("sw0002", "Mid"), ("3001", "Brick")]:
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity,"
                " condition, added_at) VALUES (?, 'minifig', ?, 1, 'used', ?)",
                (iid, name, now))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "a", True)
    return c


def test_sort_by_number(client):
    items = client.get("/api/collection?sort=number").json()["items"]
    assert [i["item_id"] for i in items] == \
        ["3001", "75335-1", "sw0002", "sw0100"]


def test_unknown_sort_falls_back_to_added(client):
    # Unbekannter Wert darf nicht crashen, sondern nutzt den Standard
    assert client.get("/api/collection?sort=quatsch").status_code == 200
