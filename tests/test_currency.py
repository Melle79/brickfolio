"""Währung und erweiterte Preisgebiete.

Die Währung ist kein Anzeigedetail: BrickLink rechnet die Preise selbst um,
also entscheidet sie mit, welche Zahl in der Datenbank landet. Wer umstellt,
muss deshalb dieselbe Nachrechen-Runde bekommen wie beim Wechsel des Gebiets –
sonst stünden alte Beträge unter neuem Zeichen. Genau das prüfen diese Tests.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "cur.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer, "
            "created_at) VALUES ('admin', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    return c


def _add(item_id, region="", waehrung="EUR"):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, price_new, price_used, price_updated_at, "
            "price_region, price_currency, added_at) VALUES (?, 'minifig', "
            "?, 1, 'used', 10, 6, ?, ?, ?, ?)",
            (item_id, item_id, now, region, waehrung, now))


# ------------------------------------------------------------ Einstellung

def test_standard_ist_euro(ctx):
    assert ctx.get("/api/settings/price_region").json()["currency"] == "EUR"


def test_waehrung_speichern_und_lesen(ctx):
    r = ctx.post("/api/settings/price_region",
                 json={"region": "GB", "currency": "GBP"})
    assert r.status_code == 200 and r.json()["currency"] == "GBP"
    assert ctx.get("/api/settings/price_region").json()["currency"] == "GBP"


def test_unbekannte_waehrung_wird_abgelehnt(ctx):
    r = ctx.post("/api/settings/price_region",
                 json={"region": "", "currency": "XYZ"})
    assert r.status_code == 400
    # und nichts wurde nebenbei umgestellt
    assert ctx.get("/api/settings/price_region").json()["currency"] == "EUR"


def test_gebiet_ohne_waehrung_laesst_die_waehrung_stehen(ctx):
    ctx.post("/api/settings/price_region",
             json={"region": "US", "currency": "USD"})
    ctx.post("/api/settings/price_region", json={"region": "CA"})
    s = ctx.get("/api/settings/price_region").json()
    assert s["region"] == "CA" and s["currency"] == "USD"


def test_neue_gebiete_stehen_zur_auswahl(ctx):
    werte = {o["value"] for o in
             ctx.get("/api/settings/price_region").json()["options"]}
    assert {"GB", "US", "CA", "AU", "north_america"} <= werte


def test_vorschlag_je_land_wird_mitgeliefert(ctx):
    s = ctx.get("/api/settings/price_region").json()
    assert s["suggested"]["GB"] == "GBP" and s["suggested"]["US"] == "USD"
    assert s["suggested"]["DE"] == "EUR"


# ------------------------------------------------------------ Nachrechnen

def test_waehrungswechsel_macht_preise_faellig(ctx):
    _add("sw0001", region="", waehrung="EUR")
    assert ctx.get("/api/settings/price_region").json()["pending"] == 0
    r = ctx.post("/api/settings/price_region",
                 json={"region": "", "currency": "USD"})
    assert r.json()["pending"] == 1


def test_alter_bestand_ohne_waehrung_gilt_als_euro(ctx):
    """Vor dieser Version gab es die Spalte nicht – solche Zeilen dürfen
    nicht plötzlich als „falsche Währung" dastehen."""
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, price_new, price_used, price_updated_at, "
            "price_region, added_at) VALUES ('sw0002', 'minifig', 'alt', 1, "
            "'used', 10, 6, ?, '', ?)", (now, now))
    assert ctx.get("/api/settings/price_region").json()["pending"] == 0


def test_config_nennt_die_waehrung(ctx):
    ctx.post("/api/settings/price_region",
             json={"region": "CH", "currency": "CHF"})
    c = ctx.get("/api/config").json()
    assert c["currency"] == "CHF" and c["price_region"] == "CH"


# ------------------------------------------------------------ Abruf

def test_waehrung_geht_an_bricklink(monkeypatch):
    gesehen = {}

    def fake_request(bl_type, item_no, condition, scope, auth,
                     waehrung="EUR"):
        gesehen["w"] = waehrung
        return {"currency_code": waehrung, "avg_price": "5",
                "unit_quantity": 3}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    out = integrations.price_guide("minifig", "sw0001", "U", scope="GB",
                                   waehrung="GBP")
    assert gesehen["w"] == "GBP" and out["currency"] == "GBP"


def test_cache_trennt_nach_waehrung(monkeypatch):
    integrations._PRICE_CACHE.clear()
    calls = []

    def fake_request(bl_type, item_no, condition, scope, auth,
                     waehrung="EUR"):
        calls.append(waehrung)
        return {"currency_code": waehrung, "avg_price": "5",
                "unit_quantity": 3}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    integrations.price_guide("minifig", "sw0009", "U", scope="",
                             use_cache=True, waehrung="EUR")
    integrations.price_guide("minifig", "sw0009", "U", scope="",
                             use_cache=True, waehrung="USD")
    assert calls == ["EUR", "USD"]      # sonst stünde ein Euro-Preis als Dollar da


# ------------------------------------------------------------ Rückfall

@pytest.mark.parametrize("land,erwartet", [
    ("US", ["US", "north_america", ""]),
    ("CA", ["CA", "north_america", ""]),
    ("GB", ["GB", "europe", ""]),
    ("AU", ["AU", "oceania", ""]),
    ("DE", ["DE", "europe", ""]),
])
def test_rueckfall_nimmt_die_eigene_region(land, erwartet):
    """Für die USA muss Nordamerika kommen, nicht Europa – sonst wäre die
    zweite Stufe für halbe Welt ein Umweg."""
    assert integrations._fallback_chain(land) == erwartet


def test_rueckfall_einer_region_geht_direkt_weltweit():
    assert integrations._fallback_chain("north_america") == ["north_america", ""]
