"""Das Preisgebiet muss mit dem Preis mitwandern.

Aus dem Betrieb: Auf der Einstellungsseite stand dauerhaft „30 Artikel haben
noch Preise aus einem anderen Gebiet" – obwohl nie ein Gebiet umgestellt
worden war. Der Zähler füllte sich selbst nach.

Der Grund: Preis, Zeitstempel und Rohdaten wanderten beim Kauf von der
Wunschliste bzw. beim Verbuchen von einer Einkaufsliste mit in die Sammlung,
`price_region` und `price_currency` aber nicht. Jeder Kauf legte damit einen
Artikel an, dessen Preis aus genau dem eingestellten Gebiet stammte, der aber
als „fremdes Gebiet" gezählt wurde. Nachrechnen half nur bis zum nächsten
Kauf – und kostete zwei BrickLink-Abrufe je Artikel für nichts.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "p.db"))
    core.init_db()
    core.set_setting("price_region", "DE")
    core.set_setting("price_currency", "EUR")
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)",
            (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


def offen() -> int:
    with core.db() as conn:
        return main._prices_pending(conn, "DE", "EUR")


def sammlung(item_id: str) -> dict:
    with core.db() as conn:
        return dict(conn.execute(
            "SELECT * FROM collection WHERE item_id = ?", (item_id,)).fetchone())


def wunsch(gebiet="DE", waehrung="EUR") -> int:
    now = int(time.time())
    with core.db() as conn:
        return conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, price_new, "
            "price_used, price_updated_at, price_region, price_currency, "
            "added_at) VALUES ('sw0970', 'minifig', 'Ugnaught', 9.5, 6.0, ?, "
            "?, ?, ?)", (now, gebiet, waehrung, now)).lastrowid


def listenposten(gebiet="DE", waehrung="EUR") -> int:
    now = int(time.time())
    with core.db() as conn:
        lid = conn.execute("INSERT INTO shopping_lists (name, created_at) "
                           "VALUES ('Flohmarkt', ?)", (now,)).lastrowid
        return conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name, "
            "qty, price_new, price_used, price_updated_at, price_region, "
            "price_currency, added_at) VALUES (?, 'sw0815', 'minifig', "
            "'Rebel Pilot', 1, 8.0, 5.0, ?, ?, ?, ?)",
            (lid, now, gebiet, waehrung, now)).lastrowid


# ------------------------------------------------------ Kauf von der Wunschliste

def test_gekaufter_wunsch_behaelt_sein_gebiet(ctx):
    wid = wunsch()
    assert ctx.post(f"/api/wanted/{wid}/acquire",
                    json={"condition": "used"}).status_code == 200
    row = sammlung("sw0970")
    assert row["price_region"] == "DE"
    assert row["price_currency"] == "EUR"


def test_gekaufter_wunsch_faellt_nicht_ins_nachrechnen(ctx):
    """Der eigentliche Schaden: der Zähler füllte sich von allein nach."""
    wid = wunsch()
    assert offen() == 0
    ctx.post(f"/api/wanted/{wid}/acquire", json={"condition": "used"})
    assert offen() == 0, "der frisch gekaufte Artikel gilt als fremdes Gebiet"


# --------------------------------------------------- Verbuchen von der Liste

def test_verbuchter_posten_behaelt_sein_gebiet(ctx):
    sid = listenposten()
    assert ctx.post(f"/api/lists/items/{sid}/receive",
                    json={"condition": "used"}).status_code == 200
    row = sammlung("sw0815")
    assert row["price_region"] == "DE"
    assert row["price_currency"] == "EUR"


def test_verbuchter_posten_faellt_nicht_ins_nachrechnen(ctx):
    sid = listenposten()
    ctx.post(f"/api/lists/items/{sid}/receive", json={"condition": "used"})
    assert offen() == 0


# ------------------------------------------------------- Echt fremd bleibt fremd

def test_wirklich_fremdes_gebiet_wird_weiter_gemeldet(ctx):
    """Die Erkennung darf nicht stumpf werden: Ein Preis aus den USA gehört
    nachgerechnet, auch wenn er über die Wunschliste hereinkommt."""
    wid = wunsch(gebiet="US", waehrung="USD")
    ctx.post(f"/api/wanted/{wid}/acquire", json={"condition": "used"})
    assert sammlung("sw0970")["price_region"] == "US"
    assert offen() == 1


def test_preisloser_wunsch_bleibt_ohne_gebiet(ctx):
    """Ohne Preis gibt es kein Gebiet zu übernehmen – und nichts zu zählen."""
    now = int(time.time())
    with core.db() as conn:
        wid = conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, added_at) "
            "VALUES ('sw1234', 'minifig', 'Ohne Preis', ?)", (now,)).lastrowid
    ctx.post(f"/api/wanted/{wid}/acquire", json={"condition": "used"})
    assert sammlung("sw1234")["price_region"] is None
    assert offen() == 0, "ohne Preis gibt es nichts umzurechnen"
