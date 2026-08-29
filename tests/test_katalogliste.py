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
    d = ctx.get("/api/katalog/liste?thema=Star Wars").json()
    nummern = [e["item_no"] for e in d["eintraege"]]
    assert "swtv001" not in nummern
    assert nummern == ["sw0001a", "sw0001b", "sw0002", "sw0003"]


def test_besitz_und_wunsch_stehen_daneben(ctx):
    d = ctx.get("/api/katalog/liste?thema=Star Wars").json()
    nach_nr = {e["item_no"]: e for e in d["eintraege"]}
    assert nach_nr["sw0002"]["besitz"] == 2
    assert nach_nr["sw0002"]["wunsch"] is False
    assert nach_nr["sw0003"]["besitz"] == 0
    assert nach_nr["sw0003"]["wunsch"] is True
    assert nach_nr["sw0001a"]["besitz"] == 0


def test_nur_fehlt_laesst_besessene_weg(ctx):
    d = ctx.get("/api/katalog/liste?thema=Star Wars&nur=fehlt").json()
    nummern = [e["item_no"] for e in d["eintraege"]]
    assert "sw0002" not in nummern
    assert d["gesamt"] == 3


def test_nur_habe_zeigt_nur_besessene(ctx):
    d = ctx.get("/api/katalog/liste?thema=Star Wars&nur=habe").json()
    assert [e["item_no"] for e in d["eintraege"]] == ["sw0002"]


def test_block_fuer_den_sprungbalken(ctx):
    d = ctx.get("/api/katalog/liste?thema=Star Wars").json()
    assert {e["block"] for e in d["eintraege"]} == {"00"}


def test_themen_zaehlen_wie_die_liste(ctx):
    """Der Kopf muss dieselbe Zahl zeigen wie die Liste darunter."""
    themen = {t["thema"]: t for t in
              ctx.get("/api/katalog/liste/themen").json()["themen"]}
    assert themen["Star Wars"]["anzahl"] == 4
    assert themen["Star Wars"]["besitz"] == 1   # Stück 2, aber eine Figur
    # `swtv` hat keinen Namen – dann steht das Kürzel als Thema da.
    assert themen["SWTV"]["anzahl"] == 1
    liste = ctx.get("/api/katalog/liste?thema=Star Wars").json()
    assert liste["gesamt"] == themen["Star Wars"]["anzahl"]


def test_suche_in_der_liste(ctx):
    d = ctx.get("/api/katalog/liste?thema=Star Wars&q=boba").json()
    assert [e["item_no"] for e in d["eintraege"]] == ["sw0002"]


# ── Markieren aus der Liste heraus ──────────────────────────────────────

def test_haken_legt_die_figur_in_die_sammlung(ctx):
    d = ctx.post("/api/katalog/marke", json={
        "item_no": "sw0001a", "marke": "habe", "an": True}).json()
    assert d["ok"] is True
    liste = ctx.get("/api/katalog/liste?thema=Star Wars").json()["eintraege"]
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
    liste = ctx.get("/api/katalog/liste?thema=Star Wars").json()["eintraege"]
    assert next(e for e in liste if e["item_no"] == "sw0001b")["wunsch"] is True


def test_aushaken_nimmt_die_einfache_zeile_zurueck(ctx):
    ctx.post("/api/katalog/marke", json={
        "item_no": "sw0001a", "marke": "habe", "an": True})
    d = ctx.post("/api/katalog/marke", json={
        "item_no": "sw0001a", "marke": "habe", "an": False}).json()
    assert d["ok"] is True and d["an"] is False
    liste = ctx.get("/api/katalog/liste?thema=Star Wars").json()["eintraege"]
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


# ── Ein Kürzel, zwei Themen – und ein Thema, viele Kürzel ───────────────

def _mehr_kataloge(conn):
    """cc ist zweigeteilt, Belville läuft unter mehreren Kürzeln."""
    _kat(conn, "cc4063", "Cameraman - Red Jacket")
    _kat(conn, "cc4443", "Soccer Player Coca-Cola Defender 1")
    _kat(conn, "cc4472", "Soccer Player Coca-Cola Secret Player B")
    _kat(conn, "belvfemale01", "Belville Female - Witch")
    _kat(conn, "belvmale01", "Belville Male - King")
    _kat(conn, "belvbaby01", "Belville Baby Princess")


def test_ein_kuerzel_zwei_themen(ctx):
    """`cc4063` ist Studios, `cc4443` Coca-Cola – dieselben zwei
    Buchstaben. Nach Kürzel gruppiert liefen beide unter einem Namen."""
    with core.db() as conn:
        _mehr_kataloge(conn)
    studios = ctx.get("/api/katalog/liste?thema=Studios").json()
    cola = ctx.get("/api/katalog/liste?thema=Coca-Cola").json()
    assert [e["item_no"] for e in studios["eintraege"]] == ["cc4063"]
    assert [e["item_no"] for e in cola["eintraege"]] == ["cc4443", "cc4472"]


def test_ein_thema_viele_kuerzel(ctx):
    """Belville steht unter vier Kürzeln. Nach Kürzel gruppiert stünde es
    viermal in der Auswahl, und jeder Eintrag zeigte ein Viertel."""
    with core.db() as conn:
        _mehr_kataloge(conn)
    themen = [t for t in ctx.get("/api/katalog/liste/themen").json()["themen"]
              if t["thema"] == "Belville"]
    assert len(themen) == 1, "Belville darf nur einmal in der Auswahl stehen"
    assert themen[0]["anzahl"] == 3
    assert themen[0]["mehrteilig"] is True
    liste = ctx.get("/api/katalog/liste?thema=Belville").json()
    assert liste["gesamt"] == 3
    # Der Sprungbalken zeigt dann die Kürzel, nicht die Ziffern: Die wären
    # bei jedem Kürzel dieselben und dazu bedeutungslos.
    # Der gemeinsame Anfang „belv" fällt weg – auf einem Handy wären
    # „BELVFEMALE" und „BELVBABY" nebeneinander zu breit, und die ersten
    # vier Buchstaben sind bei allen gleich.
    assert {e["block"] for e in liste["eintraege"]} == {
        "BABY", "FEMALE", "MALE"}


def test_kopf_des_sprungbalkens(ctx):
    """Ein Kürzel → seine Großschreibung. Mehrere → das Thema."""
    with core.db() as conn:
        _mehr_kataloge(conn)
    nach = {t["thema"]: t for t in
            ctx.get("/api/katalog/liste/themen").json()["themen"]}
    assert nach["Star Wars"]["kopf"] == "SW"
    assert nach["Belville"]["kopf"] == "Belville"


def test_unbekanntes_thema_liefert_leer(ctx):
    d = ctx.get("/api/katalog/liste?thema=Gibtsnicht").json()
    assert d["gesamt"] == 0 and d["eintraege"] == []
