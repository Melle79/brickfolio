"""Sicherung einspielen, bevor es ein Konto gibt.

Wer die Instanz umzieht, hat seine Sicherung in der Hand und braucht kein
frisches Admin-Konto – das Einspielen würde es ohnehin gleich wieder
überschreiben. Deshalb geht der Weg ohne Anmeldung, aber nur solange die
Instanz leer ist.
"""
import time
from pathlib import Path

import pytest

import core
import main
from fastapi.testclient import TestClient

INDEX = Path(__file__).resolve().parents[1] / "frontend" / "index.html"


def _sicherung(mit_admin=True, extra_user=None):
    users = []
    if mit_admin:
        users.append({"id": 1, "username": "sven", "password_hash":
                      core.hash_password("altes-passwort-123"),
                      "is_admin": 1, "is_dealer": 0,
                      "created_at": int(time.time())})
    if extra_user:
        users.append(extra_user)
    return {"app": "brickfolio", "version": 1, "created_at": int(time.time()),
            "tables": {
                "users": users,
                "collection": [{"id": 1, "item_id": "75192", "item_type": "set",
                                "name": "Millennium Falcon", "quantity": 1,
                                "condition": "used",
                                "added_at": int(time.time())}],
            }}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "setup.db"))
    core.init_db()
    return TestClient(main.app)


def _anzahl_benutzer():
    with core.db() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


def test_leere_instanz_meldet_einrichtungsbedarf(client):
    assert client.get("/api/setup").json()["needed"] is True


def test_einspielen_ohne_anmeldung(client):
    r = client.post("/api/setup/restore", json=_sicherung())
    assert r.status_code == 200
    assert r.json()["restored"]["collection"] == 1
    assert _anzahl_benutzer() == 1


def test_danach_ist_die_einrichtung_erledigt(client):
    client.post("/api/setup/restore", json=_sicherung())
    assert client.get("/api/setup").json()["needed"] is False


def test_anmelden_mit_dem_alten_passwort(client):
    """Der eigentliche Zweck: Man kommt mit den Zugangsdaten von vorher rein."""
    client.post("/api/setup/restore", json=_sicherung())
    r = client.post("/api/login", json={"username": "sven",
                                        "password": "altes-passwort-123"})
    assert r.status_code == 200
    assert r.json().get("token")


def test_keine_benutzernamen_in_der_antwort(client):
    """Der Anmeldebogen danach ist offen – dort haben Namen nichts zu suchen.

    Die Sicherung bringt sie mit, sie stehen also in der Datenbank; aber die
    Antwort trägt sie nicht nach draußen und der Bogen zeigt keine an.
    """
    r = client.post("/api/setup/restore", json=_sicherung(
        extra_user={"id": 2, "username": "paul", "password_hash": "x",
                    "is_admin": 1, "is_dealer": 0,
                    "created_at": int(time.time())}))
    assert r.status_code == 200
    assert "admins" not in r.json()
    text = r.text.lower()
    assert "sven" not in text and "paul" not in text
    # Angelegt wurden sie trotzdem – sonst käme niemand mehr hinein.
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 2


def test_anmeldebogen_nennt_keine_namen():
    """Auch im Quelltext steht keine Vorlage, die Namen einsetzen würde."""
    js = (INDEX.parent / "app.js").read_text(encoding="utf-8")
    anfang = js.index("async function setupSicherungEinspielen(")
    koerper = js[anfang:anfang + 2000]
    assert "res.admins" not in koerper
    assert 'login-user").value' not in koerper


def test_zu_sobald_ein_benutzer_existiert(client):
    """Sonst könnte jeder Fremde die Instanz jederzeit überschreiben."""
    client.post("/api/setup", json={"username": "sven",
                                    "password": "erstes-passwort"})
    r = client.post("/api/setup/restore", json=_sicherung())
    assert r.status_code == 409
    # Und der vorhandene Benutzer steht unversehrt da.
    assert _anzahl_benutzer() == 1
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM collection"
                            ).fetchone()["c"] == 0


def test_fremde_datei_wird_abgelehnt(client):
    r = client.post("/api/setup/restore",
                    json={"app": "etwas-anderes", "version": 1, "tables": {}})
    assert r.status_code in (400, 422)
    assert _anzahl_benutzer() == 0


def test_sicherung_ohne_admin_wird_abgelehnt(client):
    """Sonst stünde danach eine Instanz da, in die niemand hineinkommt."""
    r = client.post("/api/setup/restore", json=_sicherung(mit_admin=False))
    assert r.status_code == 400
    assert _anzahl_benutzer() == 0


def test_alter_weg_verlangt_weiterhin_einen_admin(client):
    """/api/restore bleibt angemeldeten Admins vorbehalten."""
    assert client.post("/api/restore", json=_sicherung()).status_code in (401,
                                                                         403)
