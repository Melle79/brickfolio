"""Tests für das wählbare Preisgebiet.

Kern ist der Rückfall: Gibt es im gewählten Land keine Verkäufe – bei
selteneren Figuren häufig –, muss der weltweite Durchschnitt einspringen,
sonst stünde der Artikel ohne Preis da.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "pr.db"))
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


def _add(item_id, region=None, priced=True):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, price_new, price_used, price_updated_at, "
            "price_region, added_at) VALUES (?, 'minifig', ?, 1, 'used', "
            "10, 6, ?, ?, ?)",
            (item_id, "Fig " + item_id, now if priced else None, region, now))


# ------------------------------------------------------------ Einstellung

def test_default_is_worldwide(ctx):
    body = ctx.get("/api/settings/price_region").json()
    assert body["region"] == ""
    assert {o["value"] for o in body["options"]} >= {"", "DE", "AT", "CH"}


def test_region_can_be_set(ctx):
    assert ctx.post("/api/settings/price_region",
                    json={"region": "DE"}).status_code == 200
    assert ctx.get("/api/settings/price_region").json()["region"] == "DE"


def test_unknown_region_refused(ctx):
    assert ctx.post("/api/settings/price_region",
                    json={"region": "XX"}).status_code == 400


# ------------------------------------------------------------ Nachrechnen

def test_pending_counts_only_other_regions(ctx):
    _add("sw0001", region=None)       # weltweit
    _add("sw0002", region="DE")
    _add("fig-9999", region=None)     # ohne BrickLink-Nr. -> zaehlt nie
    _add("sw0003", region=None, priced=False)   # nie bepreist -> zaehlt nicht
    # Aktuell weltweit: nur der DE-Eintrag weicht ab
    assert ctx.get("/api/settings/price_region").json()["pending"] == 1
    # Nach Umstellung auf DE weichen die weltweiten ab
    assert ctx.post("/api/settings/price_region",
                    json={"region": "DE"}).json()["pending"] == 1


def test_recalc_updates_and_marks_region(ctx, monkeypatch):
    _add("sw0001", region=None)
    ctx.post("/api/settings/price_region", json={"region": "DE"})

    def fake_guide(item_type, item_no, condition="U", scope=None):
        return {"currency": "EUR", "min": 1, "avg": 5.0, "max": 9,
                "times_sold": 3, "condition": condition,
                "scope": "DE", "used_scope": "DE", "fell_back": False}

    monkeypatch.setattr(integrations, "price_guide", fake_guide)
    res = ctx.post("/api/prices/refresh_region?limit=10").json()
    assert res["updated"] == 1 and res["remaining"] == 0
    with core.db() as conn:
        row = conn.execute("SELECT price_region, price_used FROM collection "
                           "WHERE item_id = 'sw0001'").fetchone()
    assert row["price_region"] == "DE" and row["price_used"] == 5.0


def test_recalc_skips_broken_entry_instead_of_looping(ctx, monkeypatch):
    """Ein Artikel, den BrickLink nicht kennt, darf den Lauf nicht blockieren."""
    _add("sw0001", region=None)
    ctx.post("/api/settings/price_region", json={"region": "DE"})

    def boom(*a, **k):
        raise LookupError("kennt BrickLink nicht")

    monkeypatch.setattr(integrations, "price_guide", boom)
    res = ctx.post("/api/prices/refresh_region?limit=10").json()
    assert res["updated"] == 0
    assert len(res["failed"]) == 1
    assert res["remaining"] == 0          # trotzdem abgehakt


# ------------------------------------------------------ Preislose nachholen

def _add_missing(item_id, age_days=1):
    """Bepreist, aber ohne Ergebnis (weder neu noch gebraucht)."""
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, price_new, price_used, price_updated_at, added_at) "
            "VALUES (?, 'minifig', ?, 1, 'used', NULL, NULL, ?, ?)",
            (item_id, "Fig " + item_id, now - age_days * 86400, now))


def test_missing_counts_only_priceless_items(ctx):
    _add("sw0001", region="")             # hat Preise -> zählt nicht
    _add_missing("sw0002")
    _add_missing("sw0003")
    with core.db() as conn:               # 0,00 zählt genauso wie NULL
        conn.execute("UPDATE collection SET price_new = 0, price_used = 0 "
                     "WHERE item_id = 'sw0003'")
    body = ctx.get("/api/settings/price_region").json()
    assert body["missing"] == 2


def test_refresh_missing_fills_from_fallback(ctx, monkeypatch):
    _add_missing("sw0002")

    def fake_guide(item_type, item_no, condition="U", scope=None):
        return {"currency": "EUR", "min": 1, "avg": 4.0, "max": 8,
                "times_sold": 2, "condition": condition,
                "scope": "", "used_scope": "", "fell_back": True}

    monkeypatch.setattr(integrations, "price_guide", fake_guide)
    res = ctx.post("/api/prices/refresh_missing?limit=10").json()
    assert res["updated"] == 1 and res["filled"] == 1 and res["remaining"] == 0
    with core.db() as conn:
        row = conn.execute("SELECT price_used FROM collection "
                           "WHERE item_id = 'sw0002'").fetchone()
    assert row["price_used"] == 4.0


def test_refresh_missing_does_not_loop_on_truly_priceless(ctx, monkeypatch):
    """Wer nirgends verkauft wurde, bleibt preislos – aber der Lauf endet."""
    _add_missing("sw0002")

    def empty_guide(item_type, item_no, condition="U", scope=None):
        return {"currency": "EUR", "min": None, "avg": None, "max": None,
                "times_sold": 0, "condition": condition,
                "scope": "", "used_scope": "", "fell_back": True}

    monkeypatch.setattr(integrations, "price_guide", empty_guide)
    res = ctx.post("/api/prices/refresh_missing?limit=10").json()
    # Abgefragt, aber nichts gefunden: nicht mehr offen für diesen Durchgang
    assert res["updated"] == 1 and res["filled"] == 0 and res["remaining"] == 0


def test_refresh_missing_skips_unknown_number(ctx, monkeypatch):
    _add_missing("sw0002")
    monkeypatch.setattr(integrations, "price_guide",
                        lambda *a, **k: (_ for _ in ()).throw(
                            LookupError("kennt BrickLink nicht")))
    res = ctx.post("/api/prices/refresh_missing?limit=10").json()
    assert len(res["failed"]) == 1 and res["remaining"] == 0


# ------------------------------------------------------------ Rückfall

def test_price_guide_falls_back_via_europe_to_worldwide(monkeypatch):
    calls = []

    def fake_request(bl_type, item_no, condition, scope, auth):
        calls.append(scope)
        if scope in ("DE", "europe"):
            return {}                       # weder DE noch Europa haben Verkäufe
        return {"currency_code": "EUR", "min_price": "2", "avg_price": "4",
                "max_price": "6", "unit_quantity": 7}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    out = integrations.price_guide("minifig", "sw0001", "U", scope="DE")
    assert calls == ["DE", "europe", ""]    # erst DE, dann Europa, dann weltweit
    assert out["avg"] == "4"
    assert out["used_scope"] == "" and out["fell_back"] is True


def test_price_guide_stops_at_europe_when_it_has_data(monkeypatch):
    """Hat Europa einen Preis, wird weltweit gar nicht erst gefragt."""
    calls = []

    def fake_request(bl_type, item_no, condition, scope, auth):
        calls.append(scope)
        if scope == "DE":
            return {"avg_price": "0.0000", "unit_quantity": 0}   # keine Verkäufe
        return {"currency_code": "EUR", "avg_price": "5", "unit_quantity": 3}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    out = integrations.price_guide("minifig", "sw0001", "U", scope="DE")
    assert calls == ["DE", "europe"]        # bei Europa ist Schluss
    assert out["avg"] == "5" and out["used_scope"] == "europe"


def test_zero_avg_string_is_not_treated_as_price(monkeypatch):
    """BrickLink liefert bei fehlenden Verkäufen avg_price='0.0000' – der
    Rückfall muss trotzdem greifen (das war der Bug hinter den 0,00-€-Fällen)."""
    calls = []

    def fake_request(bl_type, item_no, condition, scope, auth):
        calls.append(scope)
        if scope == "DE":
            return {"avg_price": "0.0000", "min_price": "0.0000",
                    "unit_quantity": 0}
        return {"currency_code": "EUR", "avg_price": "7", "unit_quantity": 4}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    out = integrations.price_guide("minifig", "sw0001", "U", scope="DE")
    assert calls[0] == "DE" and out["avg"] == "7"
    assert out["fell_back"] is True


def test_europe_setting_does_not_query_europe_twice(monkeypatch):
    """Ist Europa eingestellt, folgt direkt weltweit – kein doppelter Abruf."""
    calls = []

    def fake_request(bl_type, item_no, condition, scope, auth):
        calls.append(scope)
        return {}                           # nirgends Verkäufe

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    integrations.price_guide("minifig", "sw0001", "U", scope="europe")
    assert calls == ["europe", ""]


def test_worldwide_setting_has_no_fallback(monkeypatch):
    calls = []

    def fake_request(bl_type, item_no, condition, scope, auth):
        calls.append(scope)
        return {}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    integrations.price_guide("minifig", "sw0001", "U", scope="")
    assert calls == [""]                    # weltweit ist schon am breitesten


def test_price_guide_keeps_region_when_data_exists(monkeypatch):
    calls = []

    def fake_request(bl_type, item_no, condition, scope, auth):
        calls.append(scope)
        return {"currency_code": "EUR", "avg_price": "3.5", "unit_quantity": 2}

    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)
    out = integrations.price_guide("minifig", "sw0001", "U", scope="DE")
    assert calls == ["DE"]                  # kein zweiter Abruf noetig
    assert out["used_scope"] == "DE" and out["fell_back"] is False
