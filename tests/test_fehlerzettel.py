"""Der Zettel und der Fehlerbericht müssen zusammenpassen.

Aus dem Betrieb: Auf dem Bildschirm stand „🐞 Ein Fehler wurde
aufgezeichnet", und der Bericht dahinter war **leer**. In der Datenbank
fanden sich drei Benachrichtigungen vom Typ `error` und null Zeilen im
`error_log` – der Bericht war nach dem Ansehen geleert worden, die Zettel
blieben stehen.

Der Folgefehler war der schlimmere: `_note_error` meldet nur, wenn kein
Zettel offen ist. Ein verwaister blockierte damit **jede weitere**
Fehlermeldung. Ausgerechnet der Hinweis auf Probleme machte die App stumm.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "z.db"))
    core.init_db()
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


def zettel(offen_nur=True) -> list:
    with core.db() as conn:
        sql = "SELECT * FROM notifications WHERE kind = 'error'"
        if offen_nur:
            sql += " AND dismissed_at IS NULL"
        return [dict(r) for r in conn.execute(sql)]


def melde(ctx, nachricht="Boom", ort="app.js:1"):
    return ctx.post("/api/errors", json={"message": nachricht, "detail": "x",
                                         "context": ort})


# ------------------------------------------------------ Leeren nimmt Zettel mit

def test_leeren_raeumt_die_zettel_mit_weg(ctx):
    melde(ctx)
    assert len(zettel()) == 1, "kein Zettel angelegt"
    ctx.delete("/api/errors")
    assert ctx.get("/api/errors").json()["items"] == []
    assert zettel() == [], "Zettel blieb stehen, obwohl der Fehler weg ist"


# --------------------------------------------- Verwaiste blockieren nicht mehr

def test_ein_verwaister_zettel_blockiert_nicht(ctx):
    """Genau der Fall aus dem Betrieb: Zettel offen, Bericht leer – und
    danach kam nie wieder eine Meldung."""
    melde(ctx, "Erster")
    # Nur den Bericht leeren, den Zettel absichtlich stehen lassen.
    with core.db() as conn:
        conn.execute("DELETE FROM error_log")
    assert len(zettel()) == 1, "Aufbau des Tests stimmt nicht"

    melde(ctx, "Zweiter", "app.js:2")
    offen = zettel()
    assert len(offen) == 1, f"kein neuer Zettel: {offen}"
    with core.db() as conn:
        fp = conn.execute("SELECT fingerprint FROM error_log").fetchone()[0]
    assert offen[0]["item_id"] == fp, "der Zettel zeigt auf den alten Fehler"


def test_der_verwaiste_wird_dabei_abgeräumt(ctx):
    melde(ctx, "Erster")
    with core.db() as conn:
        conn.execute("DELETE FROM error_log")
    melde(ctx, "Zweiter", "app.js:2")
    alle = zettel(offen_nur=False)
    assert len(alle) == 2
    assert sum(1 for z in alle if z["dismissed_at"] is None) == 1, (
        "es dürfen nie zwei offene Fehlerzettel gleichzeitig herumliegen")


# ------------------------------------------------- Das alte Verhalten bleibt

def test_ein_echter_offener_zettel_blockiert_weiterhin(ctx):
    """Ein Problem löst oft mehrere Fehler aus – zehn Karten übereinander
    helfen niemandem. Solange der Fehler zum Zettel **existiert**, bleibt es
    bei einem."""
    melde(ctx, "Erster")
    melde(ctx, "Zweiter", "app.js:2")
    assert len(zettel()) == 1


def test_nach_dem_wegklicken_meldet_sich_der_naechste(ctx):
    melde(ctx, "Erster")
    z = zettel()[0]
    ctx.delete(f"/api/notifications/{z['id']}")
    melde(ctx, "Zweiter", "app.js:2")
    assert len(zettel()) == 1, "der nächste neue Fehler blieb stumm"


def test_derselbe_fehler_erzeugt_keinen_zweiten_zettel(ctx):
    melde(ctx, "Boom")
    z = zettel()[0]
    ctx.delete(f"/api/notifications/{z['id']}")
    melde(ctx, "Boom")          # identisch – nur der Zähler steigt
    assert zettel() == [], "derselbe Fehler meldete sich ein zweites Mal"
