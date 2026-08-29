"""Tests für das Durchblättern des Katalogs.

Die Liste zeigt **alle** Figuren eines Themas in Nummernfolge, mit dem
eigenen Besitzstand daneben. Zwei Dinge gehen dabei leicht schief:

- Das Kürzel `sw` fängt per `LIKE 'sw%'` auch `swtv` mit – ein anderes
  Thema, das plötzlich zwischen den Star-Wars-Figuren steht.
- Nach Besitz zu filtern, *bevor* die Sammlung dazugelesen ist, liefert
  stumm die ungefilterte Liste.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _kat(conn, nr, name, art="minifig"):
    conn.execute(
        "INSERT INTO katalog_index (item_no, item_type, name, such, img_url,"
        " category_id, jahr, updated_at) VALUES (?, ?, ?, ?, '', '65', 2011, ?)",
        (nr, art, name, main._such_norm(name), int(time.time())))


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "kl.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('sven', 'x', 1, ?)", (now,)).lastrowid
        _kat(conn, "sw0001a", "Battle Droid")
        _kat(conn, "sw0001b", "Battle Droid")
        _kat(conn, "sw0002", "Boba Fett")
        _kat(conn, "sw0003", "Darth Maul")
        # Gleicher Anfang, anderes Thema – der Stolperstein.
        _kat(conn, "swtv001", "Ezra Bridger")
        _kat(conn, "cty0001", "Polizist")
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " added_at) VALUES ('sw0002', 'minifig', 'Boba Fett', 2, ?)",
            (now,))
        conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, added_at)"
            " VALUES ('sw0003', 'minifig', 'Darth Maul', ?)", (now,))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_kuerzel_trennt_verwandte_themen(ctx):
    """`sw` darf `swtv` nicht mitnehmen."""
    d = ctx.get("/api/katalog/liste?praefix=sw").json()
    nummern = [e["item_no"] for e in d["eintraege"]]
    assert "swtv001" not in nummern
    assert nummern == ["sw0001a", "sw0001b", "sw0002", "sw0003"]


def test_besitz_und_wunsch_stehen_daneben(ctx):
    d = ctx.get("/api/katalog/liste?praefix=sw").json()
    nach_nr = {e["item_no"]: e for e in d["eintraege"]}
    assert nach_nr["sw0002"]["besitz"] == 2
    assert nach_nr["sw0002"]["wunsch"] is False
    assert nach_nr["sw0003"]["besitz"] == 0
    assert nach_nr["sw0003"]["wunsch"] is True
    assert nach_nr["sw0001a"]["besitz"] == 0


def test_nur_fehlt_laesst_besessene_weg(ctx):
    d = ctx.get("/api/katalog/liste?praefix=sw&nur=fehlt").json()
    nummern = [e["item_no"] for e in d["eintraege"]]
    assert "sw0002" not in nummern
    assert d["gesamt"] == 3


def test_nur_habe_zeigt_nur_besessene(ctx):
    d = ctx.get("/api/katalog/liste?praefix=sw&nur=habe").json()
    assert [e["item_no"] for e in d["eintraege"]] == ["sw0002"]


def test_block_fuer_den_sprungbalken(ctx):
    d = ctx.get("/api/katalog/liste?praefix=sw").json()
    assert {e["block"] for e in d["eintraege"]} == {"00"}


def test_themen_zaehlen_wie_die_liste(ctx):
    """Der Kopf muss dieselbe Zahl zeigen wie die Liste darunter."""
    themen = {t["praefix"]: t for t in ctx.get("/api/katalog/liste/themen").json()["themen"]}
    assert themen["sw"]["anzahl"] == 4
    assert themen["sw"]["besitz"] == 1      # Stück 2, aber eine Figur
    assert themen["sw"]["thema"] == "Star Wars"
    assert themen["swtv"]["anzahl"] == 1
    liste = ctx.get("/api/katalog/liste?praefix=sw").json()
    assert liste["gesamt"] == themen["sw"]["anzahl"]


def test_suche_in_der_liste(ctx):
    d = ctx.get("/api/katalog/liste?praefix=sw&q=boba").json()
    assert [e["item_no"] for e in d["eintraege"]] == ["sw0002"]


# ── Markieren aus der Liste heraus ──────────────────────────────────────

def test_haken_legt_die_figur_in_die_sammlung(ctx):
    d = ctx.post("/api/katalog/marke", json={
        "item_no": "sw0001a", "marke": "habe", "an": True}).json()
    assert d["ok"] is True
    liste = ctx.get("/api/katalog/liste?praefix=sw").json()["eintraege"]
    assert next(e for e in liste if e["item_no"] == "sw0001a")["besitz"] == 1
    with core.db() as conn:
        r = conn.execute("SELECT name, bricklink_url FROM collection"
                         " WHERE item_id = 'sw0001a'").fetchone()
    # Der Name kommt aus dem Index, nicht vom Handy.
    assert r["name"] == "Battle Droid"
    assert r["bricklink_url"].endswith("M=sw0001a")


def test_herz_legt_die_figur_auf_die_wunschliste(ctx):
    ctx.post("/api/katalog/marke", json={
        "item_no": "sw0001b", "marke": "wunsch", "an": True})
    liste = ctx.get("/api/katalog/liste?praefix=sw").json()["eintraege"]
    assert next(e for e in liste if e["item_no"] == "sw0001b")["wunsch"] is True


def test_aushaken_nimmt_die_einfache_zeile_zurueck(ctx):
    ctx.post("/api/katalog/marke", json={
        "item_no": "sw0001a", "marke": "habe", "an": True})
    d = ctx.post("/api/katalog/marke", json={
        "item_no": "sw0001a", "marke": "habe", "an": False}).json()
    assert d["ok"] is True and d["an"] is False
    liste = ctx.get("/api/katalog/liste?praefix=sw").json()["eintraege"]
    assert next(e for e in liste if e["item_no"] == "sw0001a")["besitz"] == 0


def test_aushaken_ruehrt_mehrere_stueck_nicht_an(ctx):
    """sw0002 liegt zweimal in der Sammlung – ein Fehltipper darf das nicht
    wegräumen."""
    d = ctx.post("/api/katalog/marke", json={
        "item_no": "sw0002", "marke": "habe", "an": False}).json()
    assert d["ok"] is False
    assert d["grund"] == "mehr_dahinter"
    with core.db() as conn:
        n = conn.execute("SELECT SUM(quantity) AS n FROM collection"
                         " WHERE item_id = 'sw0002'").fetchone()["n"]
    assert n == 2


def test_aushaken_ruehrt_notizen_nicht_an(ctx):
    with core.db() as conn:
        conn.execute("UPDATE collection SET quantity = 1,"
                     " notes = 'vom Flohmarkt' WHERE item_id = 'sw0002'")
    d = ctx.post("/api/katalog/marke", json={
        "item_no": "sw0002", "marke": "habe", "an": False}).json()
    assert d["ok"] is False
    with core.db() as conn:
        assert conn.execute("SELECT 1 FROM collection"
                            " WHERE item_id = 'sw0002'").fetchone()


def test_unbekannte_nummer_wird_abgewiesen(ctx):
    r = ctx.post("/api/katalog/marke", json={
        "item_no": "sw9999", "marke": "habe", "an": True})
    assert r.status_code == 404


# ── Der Sprungbalken ────────────────────────────────────────────────────

def test_der_sprung_misst_nicht_an_der_klebenden_ueberschrift():
    """Blocküberschriften kleben – ihre gemeldete Position lügt.

    `position: sticky` heißt: Alle schon durchlaufenen Überschriften
    stapeln sich unsichtbar unter der Kopfleiste, und der Browser meldet
    für jede von ihnen **diese** Position – über `getBoundingClientRect`
    genauso wie über `offsetTop`. Gemessen am 29.08.2026 lagen Block 08
    und Block 15 angeblich zwölf Pixel auseinander, obwohl 7.000 Zeilen
    dazwischenstehen. Ein Sprung nach oben rechnete daraufhin „bin schon
    da" und bewegte sich nicht.

    Gemessen wird deshalb an der ersten Zeile hinter der Überschrift. Die
    klebt nicht.
    """
    import pathlib
    import re
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "frontend" / "app.js").read_text()
    m = re.search(r"function blockAnfang\(kopf\) \{.*?\n\}\n", js, re.S)
    assert m, "blockAnfang nicht gefunden"
    f = m.group(0)
    assert "nextElementSibling" in f, \
        "Der Blockanfang muss an der ersten Zeile gemessen werden"
    # Der Fallstrick selbst: weder das eine noch das andere am Kopf.
    assert "kopf.getBoundingClientRect" not in f
    assert "offsetTop" not in f

    sprung = re.search(r"function katSpringen\(block\) \{.*?\n\}\n", js, re.S)
    assert sprung, "katSpringen nicht gefunden"
    assert "blockAnfang(" in sprung.group(0)
