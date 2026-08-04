"""Was beim vollständigen Durchlauf einer frischen Instanz auffiel.

Fünf Stellen, an denen die App etwas versprach und nicht hielt. Alle fünf
fallen im Alltag kaum auf, weil der übliche Weg über Scannen und Suchen
läuft – und dort schon eine Bildadresse mitkommt, schon ein Preis geholt
wird, schon ein Typ feststeht. Wer dagegen importiert oder wiederherstellt,
lief hinein.
"""
import io
import json
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "d.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


def eintrag(conn, item_id="sw0002", typ="minifig", bild="", preis=None,
            stand=None):
    return conn.execute(
        "INSERT INTO collection (item_id, item_type, name, img_url, quantity,"
        " condition, price_new, price_updated_at, added_at) "
        "VALUES (?, ?, 'X', ?, 1, 'used', ?, ?, ?)",
        (item_id, typ, bild, preis, stand, int(time.time()))).lastrowid


# ------------------------------------------------------ Kaufbuch in Sicherung

def test_das_kaufbuch_wird_mitgesichert(ctx):
    """Es fehlte in `BACKUP_TABLES`. Nach einer Wiederherstellung war es leer,
    während der aufsummierte Kaufpreis an der Zeile stehen blieb – man sah
    also, **dass** etwas bezahlt wurde, aber nicht mehr wann, wo und wie oft."""
    assert "purchases" in main.BACKUP_TABLES
    with core.db() as conn:
        eid = eintrag(conn)
        conn.execute(
            "INSERT INTO purchases (entry_id, quantity, unit_price, source,"
            " bought_at, note, created_at) "
            "VALUES (?, 2, 7.5, 'Flohmarkt', ?, '', ?)",
            (eid, int(time.time()), int(time.time())))
    sicherung = ctx.get("/api/backup").json()
    assert "purchases" in sicherung["tables"]
    assert len(sicherung["tables"]["purchases"]) == 1
    assert sicherung["tables"]["purchases"][0]["source"] == "Flohmarkt"


def test_das_kaufbuch_kommt_zurueck(ctx):
    with core.db() as conn:
        eid = eintrag(conn)
        conn.execute(
            "INSERT INTO purchases (entry_id, quantity, unit_price, source,"
            " bought_at, note, created_at) "
            "VALUES (?, 2, 7.5, 'Flohmarkt', ?, '', ?)",
            (eid, int(time.time()), int(time.time())))
    sicherung = ctx.get("/api/backup").json()
    with core.db() as conn:
        conn.execute("DELETE FROM purchases")
    assert ctx.post("/api/restore", json=sicherung).status_code == 200
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM purchases").fetchone()["c"] == 1


# --------------------------------------------- Preislose ohne früheren Versuch

def test_nie_versuchte_gelten_als_preislos(ctx):
    """`price_updated_at IS NOT NULL` stand in der Bedingung – gedacht als
    „schon versucht, nichts gefunden". Damit blieben ausgerechnet die
    Artikel außen vor, die noch nie versucht wurden: Ein CSV-Import legt sie
    ohne Preisstand an, und der Knopf „Preislose erneut abrufen" fand sie
    nie."""
    with core.db() as conn:
        eintrag(conn, "sw0002", preis=None, stand=None)      # nie versucht
        eintrag(conn, "sw0003", preis=None, stand=1)         # versucht, leer
        eintrag(conn, "sw0004", preis=5.0, stand=1)          # hat einen Preis
        assert main._prices_missing(conn) == 2


def test_der_lauf_greift_die_nie_versuchten_ab(ctx, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    gefragt = []

    def guide(item_type, item_no, condition="U", scope=None, **kw):
        gefragt.append(item_no)
        return {"currency": "EUR", "min": 1, "avg": 3.0, "max": 5,
                "times_sold": 2, "condition": condition, "scope": "",
                "used_scope": "", "fell_back": False}

    monkeypatch.setattr(integrations, "price_guide", guide)
    with core.db() as conn:
        eintrag(conn, "sw0002", preis=None, stand=None)
    r = ctx.post("/api/prices/refresh_missing?limit=10").json()
    assert r["updated"] == 1, f"nie versuchter Artikel übergangen: {r}"
    assert "sw0002" in gefragt


# ----------------------------------------------------- Bilder ohne Bildadresse

def test_artikel_ohne_bildadresse_zaehlen_als_offen(ctx):
    """`_bild_urls` sammelt nur, was schon eine Adresse hat. Der Bilderstand
    meldete deshalb „nichts zu tun", während jede Karte den Platzhalter
    zeigte."""
    with core.db() as conn:
        eintrag(conn, "sw0002", bild="")
        eintrag(conn, "custom-001", bild="")     # Eigenbau: kein Katalog
    d = ctx.get("/api/images/status").json()
    assert d["pending"] == 1, f"Artikel ohne Bild nicht gezählt: {d}"


def test_der_bilderlauf_traegt_adressen_nach(ctx, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "bricklink_item", lambda t, n: {
        "item_id": n, "item_type": t, "name": "X",
        "img_url": f"https://img.bricklink.com/ML/{n}.jpg"})
    monkeypatch.setattr(main, "_katalog_bild", lambda u, holen=True: None)
    with core.db() as conn:
        eid = eintrag(conn, "sw0002", bild="")
    r = ctx.post("/api/images/fetch?limit=10").json()
    assert r["resolved"] == 1, f"keine Adresse nachgetragen: {r}"
    with core.db() as conn:
        neu = conn.execute("SELECT img_url FROM collection WHERE id = ?",
                           (eid,)).fetchone()["img_url"]
    assert neu.endswith("sw0002.jpg")


def test_eigenbauten_kosten_keinen_abruf(ctx, monkeypatch):
    """Für `custom-`, `manuell-` und `fig-` hat BrickLink nichts – ein Abruf
    je Durchgang wäre reine Wartezeit."""
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    versuche = []
    monkeypatch.setattr(integrations, "bricklink_item",
                        lambda t, n: versuche.append(n) or {"img_url": ""})
    with core.db() as conn:
        for nr in ("custom-001", "manuell-7", "fig-000270"):
            eintrag(conn, nr)
    ctx.post("/api/images/fetch?limit=10")
    assert not versuche


# ------------------------------------------------- Fehler zusammenfassen

def test_derselbe_fehler_zaehlt_hoch(ctx):
    """Der Fingerabdruck nahm den **Detailtext** und ließ den Ort weg –
    genau verkehrt herum. Bei „Script error." steht im Detail die Spur der
    letzten Schritte, die jedes Mal anders aussieht: Jeder Aufruf erzeugte
    einen neuen Eintrag, statt den vorhandenen hochzuzählen."""
    for spur in ("zuletzt: Sammlung geöffnet", "zuletzt: Liste geöffnet",
                 "zuletzt: gescannt"):
        ctx.post("/api/errors", json={"message": "Script error.",
                                      "detail": spur, "context": "?:0"})
    items = ctx.get("/api/errors").json()["items"]
    assert len(items) == 1, f"nicht zusammengefasst: {[i['detail'] for i in items]}"
    assert items[0]["count"] == 3


def test_verschiedene_orte_bleiben_getrennt(ctx):
    """Sonst fiele ein echter zweiter Fehler unter den Tisch."""
    ctx.post("/api/errors", json={"message": "Boom", "detail": "x",
                                  "context": "app.js:100"})
    ctx.post("/api/errors", json={"message": "Boom", "detail": "x",
                                  "context": "app.js:200"})
    assert len(ctx.get("/api/errors").json()["items"]) == 2


# --------------------------------------------------------- CSV: Typ-Spalte

def test_csv_kennt_item_type(ctx):
    """`item_id` galt als Nummer, `item_type` aber nicht als Typ. Wer die
    eine Schreibweise nahm, bekam für die andere still „Figur" – ein Set
    landete als Minifigur, und Preise, Themen und Filter stimmten nie
    wieder."""
    csv = ("item_id,item_type,name,quantity\n"
           "75192-1,set,Millennium Falcon,1\n"
           "3001,part,Brick 2 x 4,5\n")
    r = ctx.post("/api/import/csv", json={"csv": csv})
    assert r.status_code == 200, r.text
    with core.db() as conn:
        arten = dict(conn.execute(
            "SELECT item_id, item_type FROM collection").fetchall())
    assert arten["75192-1"] == "set", f"falsch einsortiert: {arten}"
    assert arten["3001"] == "part", f"falsch einsortiert: {arten}"


def test_die_deutschen_spalten_gelten_weiter(ctx):
    csv = "Nummer;Typ;Name;Anzahl\n75192-1;Set;Falcon;1\n"
    assert ctx.post("/api/import/csv", json={"csv": csv}).status_code == 200
    with core.db() as conn:
        assert conn.execute("SELECT item_type FROM collection").fetchone()[0] == "set"
