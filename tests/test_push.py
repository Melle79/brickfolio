"""Benachrichtigung aufs Gerät (Web-Push) von der eigenen Instanz.

Zwei Dinge tragen das Ganze: Der Schlüssel der Instanz darf sich **nie**
ändern – sonst werden alle bestehenden Abonnements still ungültig –, und die
Meldung darf nichts verraten, was sie nicht muss. Der Weg führt ausdrücklich
nicht über den Tausch-Hub.
"""
import time

import pytest

import core
import main
import push
from fastapi.testclient import TestClient

ABO = {
    "endpoint": "https://push.example.test/abc123",
    "keys": {"p256dh": "BExampleKey", "auth": "Auth123"},
}


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "push.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        a = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)", (now,)).lastrowid
        k = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('kind', 'x', 0, 0, ?)", (now,)).lastrowid
    admin = TestClient(main.app)
    admin.headers["Authorization"] = "Bearer " + core.create_token(a, "admin", True)
    kid = TestClient(main.app)
    kid.headers["Authorization"] = "Bearer " + core.create_token(k, "kind", False)
    return {"admin": admin, "kid": kid, "admin_id": a}


# ------------------------------------------------------------- Schlüssel

def test_schluessel_bleibt_gleich(ctx):
    """Ein neues Paar würde alle Abonnements ungültig machen – und niemand
    erführe, warum keine Meldungen mehr ankommen."""
    a = push.public_key()
    b = push.public_key()
    assert a == b and len(a) > 80


def test_schluessel_hat_das_format_das_der_browser_verlangt(ctx):
    """`applicationServerKey` nimmt nur den rohen Kurvenpunkt in base64url –
    eine PEM-Fassung wäre dort wertlos."""
    import base64
    k = push.public_key()
    assert "-----" not in k and "=" not in k
    roh = base64.urlsafe_b64decode(k + "=" * ((4 - len(k) % 4) % 4))
    assert len(roh) == 65 and roh[0] == 0x04     # unkomprimierter Punkt


def test_privater_schluessel_verlaesst_den_server_nie(ctx):
    push.public_key()
    priv = core.get_setting(push.VAPID_PRIV)
    assert priv
    antwort = ctx["admin"].get("/api/push").text
    assert priv not in antwort
    assert "PRIVATE" not in antwort


# ------------------------------------------------------------- Abonnieren

def test_geraet_eintragen_und_wieder_loeschen(ctx):
    assert ctx["admin"].get("/api/push").json()["devices"] == []
    r = ctx["admin"].post("/api/push/subscribe", json={"subscription": ABO})
    assert r.status_code == 200
    assert len(ctx["admin"].get("/api/push").json()["devices"]) == 1
    ctx["admin"].post("/api/push/unsubscribe", json={"endpoint": ABO["endpoint"]})
    assert ctx["admin"].get("/api/push").json()["devices"] == []


def test_dasselbe_geraet_zweimal_bleibt_eins(ctx):
    """Der Browser meldet sich bei jedem Start erneut an – daraus dürfen
    keine zehn Einträge werden."""
    for _ in range(3):
        ctx["admin"].post("/api/push/subscribe", json={"subscription": ABO})
    assert len(ctx["admin"].get("/api/push").json()["devices"]) == 1


def test_abo_ohne_adresse_wird_abgelehnt(ctx):
    r = ctx["admin"].post("/api/push/subscribe",
                          json={"subscription": {"keys": {}}})
    assert r.status_code == 400


def test_nur_admins(ctx):
    assert ctx["kid"].get("/api/push").status_code == 403
    assert ctx["kid"].post("/api/push/subscribe",
                           json={"subscription": ABO}).status_code == 403


# ------------------------------------------------------------- Senden

def test_meldung_verraet_nur_dass_etwas_war(ctx, monkeypatch):
    """Auf dem Sperrbildschirm hat die Fehlermeldung nichts zu suchen."""
    ctx["admin"].post("/api/push/subscribe", json={"subscription": ABO})
    gesendet = []
    monkeypatch.setattr(push, "senden",
                        lambda t, b, u="/": gesendet.append((t, b)) or 1)
    main._note_error("TypeError: total.toFixed is not a function", "fp1")
    assert gesendet and "toFixed" not in gesendet[0][1]
    assert "Fehler" in gesendet[0][1]


def test_abgelaufenes_abo_wird_entfernt(ctx, monkeypatch):
    """Wird die App neu installiert, zeigt die alte Adresse ins Leere.
    Solche Leichen müssen weg, sonst wächst die Liste ewig."""
    ctx["admin"].post("/api/push/subscribe", json={"subscription": ABO})

    class Antwort:
        status_code = 410

    class Fehler(Exception):
        response = Antwort()

    import pywebpush
    monkeypatch.setattr(pywebpush, "WebPushException", Fehler)

    def kaputt(**kw):
        raise Fehler("weg")
    monkeypatch.setattr(pywebpush, "webpush", kaputt)
    assert push.senden("t", "b") == 0
    assert ctx["admin"].get("/api/push").json()["devices"] == []


def test_vorruebergehender_fehler_behaelt_das_abo(ctx, monkeypatch):
    """Ein Aussetzer beim Push-Dienst darf kein Gerät austragen."""
    ctx["admin"].post("/api/push/subscribe", json={"subscription": ABO})

    class Antwort:
        status_code = 503

    class Fehler(Exception):
        response = Antwort()

    import pywebpush
    monkeypatch.setattr(pywebpush, "WebPushException", Fehler)

    def kaputt(**kw):
        raise Fehler("später nochmal")
    monkeypatch.setattr(pywebpush, "webpush", kaputt)
    push.senden("t", "b")
    assert len(ctx["admin"].get("/api/push").json()["devices"]) == 1


def test_senden_ohne_geraete_tut_nichts(ctx):
    assert push.senden("t", "b") == 0


def test_probemeldung_zaehlt_die_erreichten(ctx, monkeypatch):
    ctx["admin"].post("/api/push/subscribe", json={"subscription": ABO})
    monkeypatch.setattr(push, "senden", lambda t, b, u="/": 1)
    assert ctx["admin"].post("/api/push/test").json()["sent"] == 1
