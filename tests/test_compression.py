"""Antworten werden komprimiert – bei der Sammlung macht das den Unterschied
zwischen ein paar Megabyte und ein paar Kilobyte."""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "gz.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " created_at) VALUES ('sven', 'x', 1, ?)", (now,))
        for i in range(300):
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, img_url, "
                "bricklink_url, quantity, condition, added_at) VALUES "
                "(?, 'minifig', ?, '', '', 1, 'used', ?)",
                (f"sw{i:04d}", f"Figur {i}", now))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def test_collection_is_compressed(client):
    r = client.get("/api/collection", headers={"accept-encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_compression_actually_shrinks_a_lot(client):
    """Gleichartige Datensätze schrumpfen stark – sonst stimmt etwas nicht."""
    komprimiert = client.get("/api/collection",
                             headers={"accept-encoding": "gzip"})
    roh = client.get("/api/collection", headers={"accept-encoding": "identity"})
    assert roh.headers.get("content-encoding") is None
    # httpx packt automatisch aus; die Rohgröße steht im Header.
    gz = int(komprimiert.headers["content-length"])
    assert gz < len(roh.content) / 5


def test_small_answers_stay_uncompressed(client):
    """Unter der Schwelle lohnt es nicht – dann bleibt es unverpackt."""
    r = client.get("/api/setup", headers={"accept-encoding": "gzip"})
    assert r.headers.get("content-encoding") is None
