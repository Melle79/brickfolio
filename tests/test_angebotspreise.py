"""Angebotspreise: was die Figur *kostet*, neben dem, was sie *wert* ist.

Zwei Zahlen, die leicht verwechselt werden. `guide_type=sold` sind die
Verkäufe der letzten sechs Monate, `guide_type=stock` die aktuellen
Angebote. Diese Tests halten fest, dass beide getrennt bleiben – in der
Abfrage, im Zwischenspeicher und in der Antwort.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def leerer_cache(monkeypatch):
    """Ohne Datenbank: Gebiet und Währung feststellen, Speicher leeren.

    `price_region()` und `currency()` lesen sonst Einstellungen — in den
    reinen Rechen-Tests gibt es dafür keine Datenbank.
    """
    integrations._PRICE_CACHE.clear()
    monkeypatch.setattr(integrations, "price_region", lambda: "DE")
    monkeypatch.setattr(integrations, "currency", lambda: "EUR")
    yield
    integrations._PRICE_CACHE.clear()


def _user(name, admin=True):
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, ?, ?, 0, ?)",
            (name, core.hash_password("pw1234"), int(admin), int(time.time())))
        return cur.lastrowid


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "ang.db"))
    core.init_db()
    uid = _user("anna")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    return c


def test_guide_type_geht_an_bricklink(monkeypatch):
    """Ohne den Parameter käme still der Verkaufspreis zurück."""
    gesehen = []

    def fake_request(bl_type, item_no, condition, scope, auth,
                     waehrung="EUR", guide_type="sold"):
        gesehen.append(guide_type)
        return {"min_price": "6.6975", "avg_price": "9.65",
                "total_quantity": "108", "currency_code": "EUR"}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    integrations.price_guide("minifig", "sw0003", "U", guide_type="stock")
    assert gesehen == ["stock"]


def test_angebot_liefert_billigstes_und_stueckzahl(monkeypatch):
    def fake_request(bl_type, item_no, condition, scope, auth,
                     waehrung="EUR", guide_type="sold"):
        return {"min_price": "6.6975", "avg_price": "9.6587",
                "max_price": "40.00", "total_quantity": "108",
                "unit_quantity": "37", "currency_code": "EUR"}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    d = integrations.price_guide("minifig", "sw0003", "U", guide_type="stock")
    assert d["min"] == "6.6975"
    assert d["angebote"] == "108"
    assert d["guide_type"] == "stock"
    # `times_sold` wäre hier die Zahl der Verkäufer – das ist kein Verkauf.
    assert d["times_sold"] is None


def test_ohne_angebot_wird_weiter_gesucht(monkeypatch):
    """Die Stückzahl entscheidet, nicht der Durchschnitt.

    BrickLink meldet in einem leeren Gebiet `0.0000` statt nichts. Prüfte
    man wie bei den Verkäufen auf den Durchschnitt, bliebe der Rückfall auf
    ein breiteres Gebiet aus und die Figur stünde ohne Angebot da.
    """
    gefragt = []

    def fake_request(bl_type, item_no, condition, scope, auth,
                     waehrung="EUR", guide_type="sold"):
        gefragt.append(scope)
        if scope == "DE":
            return {"min_price": "0.0000", "avg_price": "0.0000",
                    "total_quantity": "0", "currency_code": "EUR"}
        return {"min_price": "7.50", "avg_price": "9.00",
                "total_quantity": "12", "currency_code": "EUR"}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    monkeypatch.setattr(integrations, "price_region", lambda: "DE")
    d = integrations.price_guide("minifig", "sw0003", "U", guide_type="stock")
    assert gefragt[0] == "DE" and len(gefragt) > 1
    assert d["min"] == "7.50"
    assert d["fell_back"] is True


def test_zwischenspeicher_trennt_die_beiden_arten(monkeypatch):
    """Sonst bekäme der Angebotspreis den Verkaufspreis serviert."""
    antworten = {"sold": {"min_price": "8.00", "avg_price": "8.54",
                          "total_quantity": "64", "currency_code": "EUR"},
                 "stock": {"min_price": "6.69", "avg_price": "9.65",
                           "total_quantity": "108", "currency_code": "EUR"}}

    def fake_request(bl_type, item_no, condition, scope, auth,
                     waehrung="EUR", guide_type="sold"):
        return antworten[guide_type]

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    a = integrations.price_guide("minifig", "sw0003", "U", use_cache=True)
    b = integrations.price_guide("minifig", "sw0003", "U", use_cache=True,
                                 guide_type="stock")
    assert a["avg"] == "8.54" and b["min"] == "6.69"


def test_unbekannte_preisart_fliegt():
    with pytest.raises(ValueError):
        integrations.price_guide("minifig", "sw0003", "U", guide_type="quatsch")


def test_schalter_steht_voreingestellt_aus(ctx):
    assert ctx.get("/api/config").json()["angebotspreise"] is False


def test_schalter_laesst_sich_umlegen(ctx):
    ctx.post("/api/settings/angebotspreise", json={"an": True})
    assert ctx.get("/api/config").json()["angebotspreise"] is True
    ctx.post("/api/settings/angebotspreise", json={"an": False})
    assert ctx.get("/api/config").json()["angebotspreise"] is False


def test_stapelabruf_nimmt_hoechstens_60(ctx, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    viele = [{"item_type": "minifig", "item_no": f"sw{i:04d}"} for i in range(61)]
    r = ctx.post("/api/prices/angebote", json={"items": viele})
    assert r.status_code == 422        # von Pydantic abgewiesen, nicht geraten


def test_stapelabruf_ueberlebt_einen_ausfall(ctx, monkeypatch):
    """Eine Figur ohne Angebot darf die anderen nicht mitreißen."""
    import requests as rq

    def fake(item_type, item_no, condition="U", **kw):
        if item_no == "kaputt":
            raise rq.RequestException("BrickLink mag nicht")
        return {"min": "6.69", "angebote": "108", "currency": "EUR"}

    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "price_guide", fake)
    r = ctx.post("/api/prices/angebote", json={"items": [
        {"item_type": "minifig", "item_no": "kaputt"},
        {"item_type": "minifig", "item_no": "sw0003"},
    ]})
    d = r.json()["angebote"]
    assert d["minifig:kaputt:U"] is None
    assert d["minifig:sw0003:U"]["min"] == "6.69"
