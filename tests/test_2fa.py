"""Zwei-Faktor-Anmeldung: Ablauf, Notausgänge und die Fallstricke.

Der wichtigste Test ist der, dass die Zwischenmarke aus dem ersten Schritt
keine Sitzung ist – sonst wäre die ganze Prüfung wirkungslos.
"""
import json
import time

import pytest

import core
import main
import totp
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def frischer_zaehler():
    main._login_fails.clear()
    yield
    main._login_fails.clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "2fa.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin, "
                     "created_at) VALUES ('sven', ?, 1, ?)",
                     (core.hash_password("geheim12345"), now))
    return TestClient(main.app)


def anmelden(c, pw="geheim12345"):
    return c.post("/api/login", json={"username": "sven", "password": pw})


def einrichten(c):
    """Vollständige Einrichtung; gibt (Schlüssel, Rettungscodes) zurück."""
    token = anmelden(c).json()["token"]
    c.headers["Authorization"] = "Bearer " + token
    s = c.post("/api/me/2fa/start", json={"password": "geheim12345"}).json()
    r = c.post("/api/me/2fa/confirm",
               json={"code": totp.code_jetzt(s["secret"])})
    assert r.status_code == 200
    return s["secret"], r.json()["recovery_codes"]


def test_ohne_zweiten_faktor_meldet_man_sich_wie_bisher_an(client):
    d = anmelden(client).json()
    assert "token" in d and "totp_required" not in d


def test_einrichtung_verlangt_das_passwort(client):
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    r = client.post("/api/me/2fa/start", json={"password": "falsch"})
    assert r.status_code == 401


def test_einschalten_erst_nach_gueltigem_code(client):
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    s = client.post("/api/me/2fa/start",
                    json={"password": "geheim12345"}).json()
    assert client.post("/api/me/2fa/confirm",
                       json={"code": "000000"}).status_code == 401
    assert client.get("/api/me/2fa").json()["active"] is False
    client.post("/api/me/2fa/confirm", json={"code": totp.code_jetzt(s["secret"])})
    assert client.get("/api/me/2fa").json()["active"] is True


def test_anmeldung_verlangt_danach_den_zweiten_schritt(client):
    einrichten(client)
    del client.headers["Authorization"]
    d = anmelden(client).json()
    assert d.get("totp_required") is True
    assert "token" not in d and "challenge" in d


def test_zwischenmarke_ist_keine_sitzung(client):
    """Der Kern der Sache: Mit halber Anmeldung darf nichts erreichbar sein."""
    einrichten(client)
    del client.headers["Authorization"]
    challenge = anmelden(client).json()["challenge"]
    r = client.get("/api/collection",
                   headers={"Authorization": "Bearer " + challenge})
    assert r.status_code == 401


def test_richtiger_code_schliesst_die_anmeldung_ab(client):
    secret, _ = einrichten(client)
    del client.headers["Authorization"]
    ch = anmelden(client).json()["challenge"]
    # Der Code aus der Einrichtung ist verbraucht – der nächste zählt.
    naechster = totp.code_jetzt(secret, wann=time.time() + totp.SCHRITT)
    r = client.post("/api/login/2fa", json={"challenge": ch, "code": naechster})
    assert r.status_code == 200 and "token" in r.json()
    # und dieser Token taugt als Sitzung
    assert client.get("/api/collection", headers={
        "Authorization": "Bearer " + r.json()["token"]}).status_code == 200


def test_falscher_code_im_zweiten_schritt(client):
    einrichten(client)
    del client.headers["Authorization"]
    ch = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch, "code": "000000"}
                       ).status_code == 401


def test_derselbe_code_gilt_nur_einmal(client):
    secret, _ = einrichten(client)
    del client.headers["Authorization"]
    code = totp.code_jetzt(secret, wann=time.time() + totp.SCHRITT)
    ch1 = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch1, "code": code}).status_code == 200
    ch2 = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch2, "code": code}).status_code == 401


def test_rettungscode_funktioniert_und_verbraucht_sich(client):
    _, codes = einrichten(client)
    del client.headers["Authorization"]
    ch = anmelden(client).json()["challenge"]
    r = client.post("/api/login/2fa", json={"challenge": ch, "code": codes[0]})
    assert r.status_code == 200
    assert r.json()["recovery_used"] is True
    assert r.json()["recovery_left"] == 7
    # Ein zweites Mal geht derselbe nicht
    ch = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch, "code": codes[0]}
                       ).status_code == 401


def test_rettungscodes_liegen_nicht_im_klartext(client):
    _, codes = einrichten(client)
    with core.db() as conn:
        gespeichert = conn.execute(
            "SELECT totp_recovery FROM users WHERE id = 1").fetchone()[0]
    assert codes[0] not in gespeichert
    assert totp.rettungscode_hash(codes[0]) in json.loads(gespeichert)


def test_ausschalten_verlangt_passwort_und_code(client):
    secret, _ = einrichten(client)
    assert client.post("/api/me/2fa/disable",
                       json={"password": "falsch",
                             "code": totp.code_jetzt(secret)}
                       ).status_code == 401
    assert client.post("/api/me/2fa/disable",
                       json={"password": "geheim12345", "code": "000000"}
                       ).status_code == 401


def test_admin_kann_den_zweiten_faktor_abnehmen(client):
    """Notausgang bei verlorenem Telefon."""
    einrichten(client)
    assert client.post("/api/users/1/2fa/reset").status_code == 200
    assert client.get("/api/me/2fa").json()["active"] is False


def test_raten_im_zweiten_schritt_wird_gebremst(client):
    einrichten(client)
    del client.headers["Authorization"]
    ch = anmelden(client).json()["challenge"]
    for _ in range(main.LOGIN_MAX):
        client.post("/api/login/2fa", json={"challenge": ch, "code": "000000"})
    r = client.post("/api/login/2fa", json={"challenge": ch, "code": "000000"})
    assert r.status_code == 429


def test_abgelaufene_zwischenmarke_wird_abgelehnt(client):
    einrichten(client)
    alt = core.create_token(1, "sven", False, minutes=-1, zweck="2fa")
    r = client.post("/api/login/2fa", json={"challenge": alt, "code": "000000"})
    assert r.status_code == 401


def test_normaler_sitzungstoken_taugt_nicht_als_zwischenmarke(client):
    """Sonst könnte man den zweiten Schritt mit einer alten Sitzung umgehen."""
    einrichten(client)
    sitzung = client.headers["Authorization"][7:]
    r = client.post("/api/login/2fa",
                    json={"challenge": sitzung, "code": "000000"})
    assert r.status_code == 401
    assert "abgelaufen" in r.json()["detail"] or "neu" in r.json()["detail"]
