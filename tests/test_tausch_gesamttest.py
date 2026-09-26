"""Was der Tausch-Gesamttest am 26.09.2026 fand – die App-Seite.

Zwei Instanzen und ein örtlicher Hub, alle Abläufe von Beitritt bis Sperre.
Hier stehen die Fälle, in denen die App dem Hub etwas Falsches entnahm oder
etwas zuließ, das sie nicht zulassen sollte. Der Hub selbst ist gemockt.
"""
import time

import pytest
from fastapi.testclient import TestClient

import core
import hub
import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "t.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('anna', 'x', 1, 1, ?)",
            (int(time.time()),)).lastrowid
    core.set_setting("hub_token", "bft_alt")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    return c


def _trade(tid="trd_1", direction="in", status="open"):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO trades (id, direction, other_id, other_name, item_id,"
            " item_name, status, created_at, updated_at) VALUES "
            "(?, ?, 'm_bruno', 'Bruno', 'sw0188', 'Trooper', ?, ?, ?)",
            (tid, direction, status, now, now))


def _spalte(tid, name):
    with core.db() as conn:
        return conn.execute(f"SELECT {name} FROM trades WHERE id = ?",
                            (tid,)).fetchone()[0]


def _sync(client, monkeypatch, remote):
    import community
    monkeypatch.setattr(community, "_ensure_key_published", lambda: None)
    monkeypatch.setattr(community, "_meldungen_abgleichen", lambda: None)
    monkeypatch.setattr(community, "_buchungen_nachmelden", lambda *a: None)
    monkeypatch.setattr(hub, "trades", lambda: remote)
    monkeypatch.setattr(hub, "config", lambda: {
        "url": "", "member_id": "m_anna", "display_name": "Anna",
        "is_admin": False})
    return client.post("/api/hub/trades/sync")


# ------------------------------------------------ Absagen sind keine 502

@pytest.mark.parametrize("hub_status, erwartet", [
    (403, 403), (404, 404), (409, 409), (410, 410), (500, 502)])
def test_hub_absage_behaelt_ihren_status(client, monkeypatch, hub_status,
                                          erwartet):
    """Jede Absage kam als 502 an und landete als „🐞 Fehler“ im Bericht."""
    def absage(*a, **k):
        raise hub.HubError(hub_status, "nein")
    monkeypatch.setattr(hub, "own_invites", absage)
    assert client.get("/api/hub/invites").status_code == erwartet


def test_ungueltiger_hub_token_meldet_nicht_ab(client, monkeypatch):
    """Ein 401 hieße für die Oberfläche „Sitzung abgelaufen“."""
    def weg(*a, **k):
        core.set_setting("hub_verwaist", "1")
        raise hub.HubError(401, "Token fehlt oder ungültig")
    monkeypatch.setattr(hub, "own_invites", weg)
    r = client.get("/api/hub/invites")
    assert r.status_code == 409
    assert "kennt diese Instanz nicht mehr" in r.json()["detail"]
    assert client.get("/api/hub").json()["verwaist"] is True


# ------------------------------------------------ Beitreten

def test_zweiter_beitritt_wird_abgelehnt(client, monkeypatch):
    aufgerufen = []
    monkeypatch.setattr(hub, "connect_with_invite",
                        lambda *a: aufgerufen.append(a))
    r = client.post("/api/hub/connect",
                    json={"invite_code": "bfi_x", "display_name": "Anna Zwei"})
    assert r.status_code == 409 and not aufgerufen


def test_abmelden_macht_gespraeche_zu_ehemaligen(client, monkeypatch):
    """Nach dem Wiederbeitritt standen alle als „vom Gegenüber gelöscht“."""
    _trade(status="closed")
    monkeypatch.setattr(hub, "leave", lambda: None)
    client.post("/api/hub/disconnect")
    core.set_setting("hub_token", "bft_neu")
    assert _sync(client, monkeypatch, []).status_code == 200
    assert _spalte("trd_1", "status") == "closed"
    assert _spalte("trd_1", "ehemalig") == 1


# ------------------------------------------------ Gelöschte Gespräche

def test_zugesagtes_gespraech_bleibt_buchbar_nach_loeschung(client,
                                                             monkeypatch):
    _trade(status="accepted")
    _trade("trd_2", status="open")
    assert _sync(client, monkeypatch, []).status_code == 200
    assert _spalte("trd_1", "status") == "accepted"
    assert _spalte("trd_1", "entfernt") == 1
    assert _spalte("trd_2", "status") == "removed"


# ------------------------------------------------ Statuswechsel

@pytest.mark.parametrize("richtung, stand, ziel, ok", [
    ("in", "open", "accepted", True),
    ("out", "open", "accepted", False),     # eigene Anfrage annehmen
    ("in", "declined", "accepted", False),
    ("in", "closed", "open", False),
    ("in", "accepted", "closed", True),
])
def test_statuswechsel_wird_geprueft(client, monkeypatch, richtung, stand,
                                      ziel, ok):
    _trade(direction=richtung, status=stand)
    monkeypatch.setattr(hub, "set_trade_status", lambda *a: None)
    r = client.post("/api/hub/trades/trd_1/status", json={"status": ziel})
    assert (r.status_code == 200) is ok


def test_leere_nachricht_wird_abgelehnt(client):
    _trade()
    r = client.post("/api/hub/trades/trd_1/messages", json={"text": "   "})
    assert r.status_code == 422


# ------------------------------------------------ Schlüssel eines Gesperrten

def test_gesperrtes_gegenueber_bekommt_die_nachricht(client, monkeypatch):
    """Der Hub gibt Schlüssel nur für aktive Mitglieder – der gemerkte gilt."""
    import community
    import crypto_box
    crypto_box.remember_key("m_bruno", "SCHLUESSEL", "Bruno")

    def weg(member_id):
        raise hub.HubError(404, "Mitglied nicht gefunden")
    monkeypatch.setattr(hub, "member_key", weg)
    assert community._fremder_schluessel("m_bruno") == "SCHLUESSEL"
