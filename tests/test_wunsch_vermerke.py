"""Die Wunschliste soll sagen, was ihr schon habt oder schon geplant habt.

Ein Wunsch ist eine Kaufabsicht. Zwei Dinge machen sie hinfällig, und beide
stehen woanders in der App: das Stück liegt längst in der Sammlung, oder es
steht schon auf einer offenen Einkaufsliste. Ohne Vermerk kauft man es ein
zweites Mal – im Zweifel auf demselben Flohmarkt.

Die Wunschliste selbst bleibt bewusst frei von Grün-Logik: Sie ist die Liste
dessen, was ihr *wollt*. Der Vermerk erklärt nur den Einzelfall.
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
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


def wuensch(ctx, item_id="sw0970", name="Ugnaught"):
    with core.db() as conn:
        conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, added_at) "
            "VALUES (?, 'minifig', ?, ?)", (item_id, name, int(time.time())))


def liste(name="Flohmarkt", archived=0) -> int:
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO shopping_lists (name, archived, created_at) "
            "VALUES (?, ?, ?)", (name, archived, int(time.time())))
        return cur.lastrowid


def drauf(lid, item_id="sw0970", qty=1, done=0):
    with core.db() as conn:
        conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name, "
            "qty, done, added_at) VALUES (?, ?, 'minifig', 'Ugnaught', ?, ?, ?)",
            (lid, item_id, qty, done, int(time.time())))


def erster(ctx) -> dict:
    return ctx.get("/api/wanted").json()["items"][0]


# ------------------------------------------------------------- Einkaufsliste

def test_wunsch_auf_offener_liste_wird_vermerkt(ctx):
    wuensch(ctx)
    drauf(liste("Flohmarkt"))
    it = erster(ctx)
    assert it["on_lists"] == ["Flohmarkt"]
    assert it["on_lists_qty"] == 1


def test_ohne_liste_bleibt_der_vermerk_leer(ctx):
    wuensch(ctx)
    assert erster(ctx)["on_lists"] == []


def test_mehrere_listen_werden_alle_genannt(ctx):
    wuensch(ctx)
    drauf(liste("Flohmarkt"))
    drauf(liste("Bremen"), qty=2)
    it = erster(ctx)
    assert sorted(it["on_lists"]) == ["Bremen", "Flohmarkt"]
    assert it["on_lists_qty"] == 3, "die Stückzahlen aller Listen zählen zusammen"


def test_abgehakter_posten_zaehlt_nicht_mehr(ctx):
    """Abgehakt heißt gekauft – dann ist der Posten nicht mehr unterwegs."""
    wuensch(ctx)
    drauf(liste("Flohmarkt"), done=1)
    assert erster(ctx)["on_lists"] == []


def test_archivierte_liste_zaehlt_nicht_mehr(ctx):
    wuensch(ctx)
    drauf(liste("Letztes Jahr", archived=1))
    assert erster(ctx)["on_lists"] == []


def test_gleiche_nummer_anderer_typ_zaehlt_nicht(ctx):
    """`3001` ist Set *und* Stein. Der Vermerk darf nicht überspringen."""
    wuensch(ctx, "3001", "Brick 2x4")
    lid = liste("Steine")
    with core.db() as conn:
        conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name, "
            "qty, done, added_at) VALUES (?, '3001', 'set', 'Sonstiges', "
            "1, 0, ?)", (lid, int(time.time())))
    assert erster(ctx)["on_lists"] == []


# ------------------------------------------------------------------ Sammlung

def test_besitz_wird_weiterhin_vermerkt(ctx):
    wuensch(ctx)
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "added_at) VALUES ('sw0970', 'minifig', 'Ugnaught', 2, ?)",
            (int(time.time()),))
    assert erster(ctx)["owned"] == 2


def test_beide_vermerke_gleichzeitig(ctx):
    """Gekauft *und* noch auf der Liste – beides gehört an die Karte, sonst
    räumt niemand die Liste auf."""
    wuensch(ctx)
    drauf(liste("Flohmarkt"))
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "added_at) VALUES ('sw0970', 'minifig', 'Ugnaught', 1, ?)",
            (int(time.time()),))
    it = erster(ctx)
    assert it["owned"] == 1
    assert it["on_lists"] == ["Flohmarkt"]
