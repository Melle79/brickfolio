"""Bremse vor dem Erkennungsdienst (/api/scan).

Brickognize stellt seine Erkennung kostenlos bereit. Ein Foto kostet eine
Anfrage, mit Ausschnitten ein paar mehr – was hier verhindert wird, ist der
Ausreißer: eine Schleife, die aus einem Regalfoto vierzig Anfragen macht.
Die Grenze sitzt im Server, damit sie für alle Benutzer der Instanz gilt und
auch dann greift, wenn jemand an der Oberfläche vorbei anfragt.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "scan.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    monkeypatch.setattr(integrations, "recognize",
                        lambda raw: {"items": [], "listing_id": None, "box": None})
    main._scan_zeiten.clear()
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def _scan(client):
    return client.post("/api/scan",
                       files={"file": ("scan.jpg", b"xxx", "image/jpeg")})


def test_normales_foto_geht_durch(client):
    """Ein Foto mit fünf Figuren sind sechs Anfragen – der Normalfall."""
    for _ in range(6):
        assert _scan(client).status_code == 200


def test_ausreisser_wird_gebremst(client):
    ok = sum(1 for _ in range(main.SCAN_MAX + 10) if _scan(client).status_code == 200)
    assert ok == main.SCAN_MAX
    r = _scan(client)
    assert r.status_code == 429
    assert "kostenlos" in r.json()["detail"]


def test_kontingent_laeuft_wieder_voll(client, monkeypatch):
    for _ in range(main.SCAN_MAX):
        _scan(client)
    assert _scan(client).status_code == 429
    # Fenster vorbei: Die alten Einträge fallen heraus.
    main._scan_zeiten[:] = [t - main.SCAN_FENSTER - 1 for t in main._scan_zeiten]
    assert _scan(client).status_code == 200


def test_gebremste_anfrage_erreicht_den_dienst_nicht(client, monkeypatch):
    """Abgewiesen heißt abgewiesen – nicht erst hinschicken und dann verwerfen."""
    gerufen = []
    monkeypatch.setattr(integrations, "recognize",
                        lambda raw: gerufen.append(1) or {"items": []})
    for _ in range(main.SCAN_MAX):
        _scan(client)
    vorher = len(gerufen)
    assert _scan(client).status_code == 429
    assert len(gerufen) == vorher
