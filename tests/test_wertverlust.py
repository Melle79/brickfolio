"""Verluste gehören in eine eigene Liste.

Bisher gab es nur „Beste Wertsteigerungen": alles mit Kaufpreis, nach Gewinn
absteigend, die ersten fünf. Verluste rutschten dort nur hinein, wenn es
**weniger als fünf Gewinner** gab.

Damit sah man sie ausgerechnet dann nicht, wenn die Sammlung groß genug war,
um interessant zu sein – und wenn man sie sah, standen sie unter einer
Überschrift, die das Gegenteil versprach.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "w.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)",
            (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


def artikel(name, bezahlt, wert):
    """Ein Stück mit Kaufpreis und aktuellem Gebrauchtwert."""
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " condition, price_used, paid_price, paid_source, added_at)"
            " VALUES (?, 'minifig', ?, 1, 'used', ?, ?, 'manual', ?)",
            (name.lower().replace(" ", ""), name, wert, bezahlt,
             int(time.time())))


def zahlen(ctx) -> dict:
    return ctx.get("/api/stats/dashboard").json()


# ---------------------------------------------------------------- Trennung

def test_verluste_stehen_in_ihrer_eigenen_liste(ctx):
    artikel("Gewinner", bezahlt=10, wert=25)
    artikel("Verlierer", bezahlt=40, wert=15)
    d = zahlen(ctx)
    assert [w["name"] for w in d["winners"]] == ["Gewinner"]
    assert [v["name"] for v in d["losers"]] == ["Verlierer"]


def test_der_groesste_verlust_steht_oben(ctx):
    artikel("Klein", bezahlt=12, wert=10)      # −2
    artikel("Gross", bezahlt=90, wert=20)      # −70
    artikel("Mittel", bezahlt=30, wert=10)     # −20
    d = zahlen(ctx)
    assert [v["name"] for v in d["losers"]] == ["Gross", "Mittel", "Klein"]
    assert d["losers"][0]["gain"] == -70


def test_gewinne_enthalten_keine_verluste_mehr(ctx):
    """Ein rotes Minus unter „Beste Wertsteigerungen" war immer schon
    seltsam – und passierte, sobald es weniger als fünf Gewinner gab."""
    artikel("Einziger Gewinner", bezahlt=5, wert=9)
    for i in range(4):
        artikel(f"Verlierer {i}", bezahlt=50, wert=5)
    d = zahlen(ctx)
    assert all(w["gain"] > 0 for w in d["winners"]), d["winners"]
    assert len(d["losers"]) == 4


def test_verluste_werden_auch_bei_vielen_gewinnern_gezeigt(ctx):
    """Genau der Fall, der vorher unsichtbar blieb."""
    for i in range(8):
        artikel(f"Gewinner {i}", bezahlt=5, wert=50)
    artikel("Fehlkauf", bezahlt=200, wert=30)
    d = zahlen(ctx)
    assert len(d["winners"]) == 5
    assert [v["name"] for v in d["losers"]] == ["Fehlkauf"]


# ------------------------------------------------------------------ Ränder

def test_ohne_verluste_bleibt_die_liste_leer(ctx):
    artikel("Gewinner", bezahlt=10, wert=25)
    assert zahlen(ctx)["losers"] == []


def test_wer_genau_null_gemacht_hat_steht_nirgends(ctx):
    """Weder gewonnen noch verloren – beide Listen sind für Bewegung da."""
    artikel("Nullsummenspiel", bezahlt=20, wert=20)
    d = zahlen(ctx)
    assert d["winners"] == [] and d["losers"] == []


def test_ohne_kaufpreis_kein_verlust(ctx):
    """Ohne Kaufpreis gibt es nichts zu vergleichen."""
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " condition, price_used, added_at) VALUES ('sw1', 'minifig',"
            " 'Ohne Kaufpreis', 1, 'used', 5, ?)", (int(time.time()),))
    assert zahlen(ctx)["losers"] == []


def test_hoechstens_fuenf(ctx):
    for i in range(9):
        artikel(f"Fehlkauf {i}", bezahlt=100 + i, wert=1)
    assert len(zahlen(ctx)["losers"]) == 5


def test_die_liste_traegt_alles_fuer_den_steckbrief(ctx):
    """Ein Tipp auf den Namen soll den Steckbrief öffnen – dafür braucht die
    Zeile Nummer und Typ, nicht nur einen Namen."""
    artikel("Fehlkauf", bezahlt=90, wert=20)
    eintrag = zahlen(ctx)["losers"][0]
    for feld in ("item_id", "item_type", "name", "img_url"):
        assert feld in eintrag, f"{feld} fehlt für den Steckbrief"
