"""Grundabsicherung: Passwortraten bremsen, Schutz-Header setzen.

Wichtig, sobald jemand die App über eine Portfreigabe erreichbar macht –
im Heimnetz fällt beides nicht auf, draußen sehr wohl.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def frischer_zaehler():
    main._login_fails.clear()
    yield
    main._login_fails.clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "sec.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin, "
                     "created_at) VALUES ('sven', ?, 1, ?)",
                     (core.hash_password("richtig123"), now))
    return TestClient(main.app)


def test_falsches_passwort_wird_abgelehnt(client):
    r = client.post("/api/login", json={"username": "sven", "password": "x"})
    assert r.status_code == 401


def test_raten_wird_nach_zehn_versuchen_gebremst(client):
    for _ in range(main.LOGIN_MAX):
        client.post("/api/login", json={"username": "sven", "password": "x"})
    r = client.post("/api/login", json={"username": "sven", "password": "x"})
    assert r.status_code == 429
    assert "Fehlversuche" in r.json()["detail"]


def test_bremse_gilt_auch_bei_richtigem_passwort(client):
    """Sonst könnte man die Sperre mit dem erratenen Passwort sofort umgehen."""
    for _ in range(main.LOGIN_MAX):
        client.post("/api/login", json={"username": "sven", "password": "x"})
    r = client.post("/api/login",
                    json={"username": "sven", "password": "richtig123"})
    assert r.status_code == 429


def test_erfolgreiche_anmeldung_setzt_den_zaehler_zurueck(client):
    for _ in range(main.LOGIN_MAX - 1):
        client.post("/api/login", json={"username": "sven", "password": "x"})
    assert client.post("/api/login",
                       json={"username": "sven", "password": "richtig123"}
                       ).status_code == 200
    # Danach wieder volle Anzahl Versuche
    for _ in range(main.LOGIN_MAX - 1):
        assert client.post("/api/login",
                           json={"username": "sven", "password": "x"}
                           ).status_code == 401


def test_zaehlung_je_konto_traegt_ueber_adressen_hinweg(client):
    """Ein Wechsel der Herkunft darf die Kontosperre nicht aushebeln."""
    for i in range(main.LOGIN_MAX):
        client.post("/api/login", json={"username": "sven", "password": "x"},
                    headers={"x-forwarded-for": f"10.0.0.{i}"})
    r = client.post("/api/login", json={"username": "sven", "password": "x"},
                    headers={"x-forwarded-for": "10.0.0.99"})
    assert r.status_code == 429


def test_schutz_header_auf_der_startseite(client):
    h = client.get("/").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "SAMEORIGIN"
    assert "default-src 'self'" in h["content-security-policy"]


def test_katalogbilder_bleiben_erlaubt(client):
    """Ohne diese Ausnahme bliebe der halbe Katalog leer."""
    csp = client.get("/").headers["content-security-policy"]
    assert "img.bricklink.com" in csp and "cdn.rebrickable.com" in csp


def test_api_antworten_tragen_die_basis_header(client):
    h = client.get("/api/setup").headers
    assert h["x-content-type-options"] == "nosniff"
