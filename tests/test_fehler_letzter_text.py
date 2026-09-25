"""Ein wiederkehrender Fehler behält beides: den ersten und den jüngsten Text.

Gleichartige Fehler werden über den Fingerabdruck zusammengefasst, damit ein
wiederkehrendes Problem die Liste nicht flutet. Bis 2.88.14 blieb dabei der
Detailtext des **ersten** Auftretens stehen – ein Wiedersehen erhöhte nur
den Zähler.

Das kostete am 23.09.2026 eine Runde: In der Liste stand ein Eintrag mit
Fassung 2.88.7, und ihm war nicht anzusehen, ob er von vor oder nach der
Behebung stammte. Beides ist nützlich – der erste Text zeigt, womit es
anfing, der jüngste, ob es noch auftritt.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "d.db"))
    core.init_db()
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('anna', 'x', 1, 1, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    return c


def _melde(client, detail, version):
    r = client.post("/api/errors", json={
        "message": "Etwas ging schief", "detail": detail,
        "context": "probe", "app_version": version})
    assert r.status_code == 200


def test_der_erste_text_bleibt(client):
    _melde(client, "so fing es an", "2.88.0")
    _melde(client, "so sieht es heute aus", "2.88.9")
    e = client.get("/api/errors").json()["items"][0]
    assert e["detail"] == "so fing es an"
    assert e["app_version"] == "2.88.0"


def test_der_juengste_kommt_dazu(client):
    _melde(client, "so fing es an", "2.88.0")
    _melde(client, "so sieht es heute aus", "2.88.9")
    e = client.get("/api/errors").json()["items"][0]
    assert e["last_detail"] == "so sieht es heute aus"
    assert e["last_version"] == "2.88.9"
    assert e["count"] == 2


def test_beim_ersten_mal_gibt_es_noch_keinen_juengsten(client):
    """Sonst stünde derselbe Text zweimal untereinander."""
    _melde(client, "einmalig", "2.88.9")
    e = client.get("/api/errors").json()["items"][0]
    assert e["detail"] == "einmalig"
    assert not e["last_detail"]


def test_die_alte_datenbank_bekommt_die_spalten(client):
    """Bestehende Instanzen dürfen daran nicht scheitern."""
    with core.db() as conn:
        spalten = {r[1] for r in conn.execute("PRAGMA table_info(error_log)")}
    assert {"last_detail", "last_version"} <= spalten
