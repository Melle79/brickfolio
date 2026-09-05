"""Tests für die Katalogsuche (Mindestlänge, Seitenweitergabe) und die
Kennzahl „Preisabruf älter als 7 Tage" im Preis-Protokoll.
"""
import time
from pathlib import Path

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "cat.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer, "
            "created_at) VALUES ('tester', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = (
        "Bearer " + core.create_token(uid, "tester", True))
    return c


# ------------------------------------------------------------ Katalogsuche

@pytest.fixture
def catalog(monkeypatch):
    """Simuliert Rebrickable und merkt sich die übergebenen Argumente."""
    calls = []

    def fake_search(query, item_type="minifig", page=1, page_size=10):
        calls.append({"query": query, "item_type": item_type,
                      "page": page, "page_size": page_size})
        start = (page - 1) * page_size
        total = 23
        items = [{"item_id": f"fig-{n:04d}", "item_type": item_type,
                  "name": f"Treffer {n}", "img_url": "", "sub": "",
                  "year": 0, "bricklink_url": ""}
                 for n in range(start, min(start + page_size, total))]
        return {"items": items, "count": total, "page": page,
                "page_size": page_size,
                "has_more": start + len(items) < total}

    monkeypatch.setattr(integrations, "rebrickable_enabled", lambda: True)
    monkeypatch.setattr(integrations, "search_catalog", fake_search)
    return calls


def test_search_needs_three_characters(client, catalog):
    for q in ("", "a", "at"):
        r = client.get(f"/api/search?q={q}")
        assert r.status_code == 200
        assert r.json()["items"] == []
    assert catalog == []        # gar nicht erst abgefragt


def test_search_runs_from_three_characters(client, catalog):
    r = client.get("/api/search?q=yod")
    assert r.status_code == 200
    assert len(catalog) == 1 and catalog[0]["query"] == "yod"


def test_search_first_page_has_ten_and_more(client, catalog):
    body = client.get("/api/search?q=trooper").json()
    assert len(body["items"]) == 10
    assert body["count"] == 23 and body["has_more"] is True
    assert catalog[0]["page"] == 1


def test_search_passes_page_through(client, catalog):
    body = client.get("/api/search?q=trooper&page=3").json()
    assert catalog[0]["page"] == 3
    assert len(body["items"]) == 3          # Rest der 23
    assert body["has_more"] is False


def test_search_without_key_is_not_configured(client, monkeypatch):
    monkeypatch.setattr(integrations, "rebrickable_enabled", lambda: False)
    assert client.get("/api/search?q=yoda").status_code == 501


# ------------------------------------------------------------ Preis-Protokoll

def _add(conn, item_id, price_updated_at):
    conn.execute(
        "INSERT INTO collection (item_id, item_type, name, quantity, "
        "condition, price_new, price_used, price_updated_at, added_at) "
        "VALUES (?, 'minifig', ?, 1, 'used', 10, 6, ?, ?)",
        (item_id, "Fig " + item_id, price_updated_at, int(time.time())))


def test_pricelog_counts_only_stale_real_items(client):
    now = int(time.time())
    old = now - 10 * 86400          # älter als 7 Tage
    fresh = now - 86400
    with core.db() as conn:
        _add(conn, "sw0001", old)
        _add(conn, "sw0002", old)
        _add(conn, "sw0100", fresh)      # frisch
        _add(conn, "sw0200", None)       # nie abgerufen -> zählt nicht
        _add(conn, "fig-9999", old)      # ohne BrickLink-Nr. -> zählt nicht
    body = client.get("/api/price_log").json()
    assert body["stale_count"] == 2
    assert body["stale_days"] == 7


def test_pricelog_zero_when_all_fresh(client):
    with core.db() as conn:
        _add(conn, "sw0001", int(time.time()) - 3600)
    assert client.get("/api/price_log").json()["stale_count"] == 0


# ------------------------------------------------------ Abzeichen der Suche

def test_suggest_info_covers_more_than_one_page(client):
    """Bei 10 Treffern pro Seite plus Nachladen müssen auch spätere
    Treffer ihr „vorhanden/fehlt"-Abzeichen bekommen (früher nur 8)."""
    with core.db() as conn:
        _add(conn, "sw0012", None)
    items = [{"item_id": f"sw{n:04d}", "item_type": "minifig"}
             for n in range(20)]
    r = client.post("/api/suggest_info", json={"items": items})
    assert r.status_code == 200, r.text
    info = r.json()
    assert len(info) == 20
    assert info["sw0012"]["owned"] == 1          # der 13. Treffer
    assert info["sw0000"]["owned"] == 0


def test_suggest_info_rejects_absurd_amounts(client):
    items = [{"item_id": f"sw{n:04d}", "item_type": "minifig"}
             for n in range(200)]
    assert client.post("/api/suggest_info", json={"items": items}
                       ).status_code == 422


# ── Der Hintergrund-Refresh muss die Sammlung schaffen ────────────────
#
# Am 05.09.2026 stand in Svens Preis-Protokoll: „Bei 328 Artikeln ist der
# Preisabruf älter als 7 Tage." Das war kein Fehler, sondern Arithmetik:
# feste 40 Einträge je Lauf, zwei Läufe am Tag – 80 Preise täglich bei 926
# Artikeln. Jeder kam nur alle 11,6 Tage dran, also war dauerhaft ein
# Drittel überfällig. Gemessen an der Altersverteilung: genau 80 je Tag.

def test_der_stapel_reicht_fuer_die_ganze_sammlung():
    """Ein Lauf muss so viel nehmen, dass in sieben Tagen alles drankommt –
    sonst wächst der Rückstand, und die Anzeige meldet ihn für immer."""
    tage = main.PRICE_STALE_SECONDS / 86400
    for anzahl in (300, 926, 2000, 5000):
        stapel = main.preis_stapel(anzahl)
        schafft = stapel * main.PRICE_LAEUFE_JE_TAG * tage
        if stapel < main.PRICE_STAPEL_MAX:
            assert schafft >= anzahl, (
                "%d Artikel: %d je Lauf schaffen nur %d in %g Tagen"
                % (anzahl, stapel, schafft, tage))


def test_kleine_sammlungen_bleiben_beim_alten_takt():
    """Wer wenig hat, soll BrickLink nicht öfter behelligen als nötig."""
    assert main.preis_stapel(0) == main.PRICE_STAPEL_MIN
    assert main.preis_stapel(50) == main.PRICE_STAPEL_MIN


def test_der_deckel_schuetzt_das_kontingent():
    """Auch eine riesige Sammlung darf den Zugang nicht sprengen."""
    assert main.preis_stapel(10 ** 6) == main.PRICE_STAPEL_MAX
    rufe = main.PRICE_STAPEL_MAX * main.PRICE_LAEUFE_JE_TAG * 2
    assert rufe <= 2000, "%d BrickLink-Rufe am Tag sind zu viel" % rufe


def test_die_aeltesten_kommen_zuerst_dran():
    """Ohne `ORDER BY` entscheidet die Zeilennummer. Ein Artikel, dessen
    Abruf dauernd scheitert, behält seinen alten Zeitstempel und läge in
    jedem Lauf wieder vorn – die dahinter kämen nie an die Reihe."""
    quelle = (Path(__file__).resolve().parents[1] / "backend"
              / "main.py").read_text()
    block = quelle.split("def _price_refresher")[1]
    block = block[:block.index("for row in rows")]
    assert "ORDER BY COALESCE(price_updated_at, 0)" in block
    assert "LIMIT 40" not in block, "der feste Stapel ist wieder da"
