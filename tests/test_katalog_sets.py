"""Sets im Katalog – sie tragen ihr Thema nicht in der Nummer.

`sw1213` sagt „Star Wars". `75192-1` sagt nichts. Bei Sets steht das Thema
allein in der BrickLink-Kategorie, und die kommt als Nummer. Deshalb der
Kategoriebaum.

Und: Bis 2.65.1 warf der Dateiimport alles weg, was keine Minifigur war –
Svens Sets.xml wurde vollständig verworfen, mit der Meldung, es sei die
falsche Datei.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "ks.db"))
    core.init_db()
    main._kategorien_cache.clear()
    now = int(time.time())
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('sven', 'x', 1, ?)", (now,)).lastrowid
        # Ein Baum wie bei BrickLink: „Star Wars" mit Unterkategorien.
        for cid, name, eltern in (("65", "Star Wars", ""),
                                  ("263", "Star Wars Episode 1", "65"),
                                  ("67", "Town", ""),
                                  ("161", "City", "67")):
            conn.execute(
                "INSERT INTO katalog_kategorien (id, name, parent_id,"
                " geholt_at) VALUES (?, ?, ?, ?)", (cid, name, eltern, now))
        for nr, kat, name in (("75192-1", "65", "Millennium Falcon"),
                              ("7141-1", "263", "Naboo Fighter"),
                              ("60380-1", "161", "Downtown")):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such,"
                " img_url, category_id, jahr, updated_at)"
                " VALUES (?, 'set', ?, ?, '', ?, 2017, ?)",
                (nr, name, main._such_norm(name), kat, now))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_sets_bekommen_ihr_thema_aus_der_kategorie(ctx):
    assert main._thema_von("75192-1", "65") == "Star Wars"
    assert main._thema_von("60380-1", "161") == "Town"


def test_unterkategorien_landen_unter_dem_dach(ctx):
    """„Star Wars ▸ Episode I" gehört zu Star Wars – sonst stünden in der
    Auswahl hunderte Zweige mit je einer Handvoll Sets."""
    assert main._thema_von("7141-1", "263") == "Star Wars"


def test_die_auswahl_zeigt_die_set_themen(ctx):
    d = ctx.get("/api/katalog/liste/themen?art=set").json()
    nach = {t["thema"]: t for t in d["themen"]}
    assert nach["Star Wars"]["anzahl"] == 2
    assert nach["Town"]["anzahl"] == 1
    assert d["arten"]["set"] == 3


def test_die_liste_liefert_die_sets_des_themas(ctx):
    d = ctx.get("/api/katalog/liste?thema=Star Wars&art=set").json()
    assert sorted(e["item_no"] for e in d["eintraege"]) == ["7141-1", "75192-1"]
    # Kein Kürzel-Vorfilter: Bei Sets entscheidet allein die Kategorie.
    assert d["gesamt"] == 2


def test_ohne_kategoriebaum_bleibt_das_thema_leer(ctx):
    """Lieber gar kein Thema als ein erfundenes."""
    with core.db() as conn:
        conn.execute("DELETE FROM katalog_kategorien")
    main._kategorien_cache.clear()
    assert main._thema_von("75192-1", "65") == ""


def test_der_import_nimmt_jetzt_auch_sets(ctx):
    xml = """<?xml version="1.0"?><CATALOG>
      <ITEM><ITEMTYPE>S</ITEMTYPE><ITEMID>10179-1</ITEMID>
        <ITEMNAME>Ultimate Collector's Millennium Falcon</ITEMNAME>
        <CATEGORY>65</CATEGORY><ITEMYEAR>2007</ITEMYEAR></ITEM>
      <ITEM><ITEMTYPE>M</ITEMTYPE><ITEMID>sw0001a</ITEMID>
        <ITEMNAME>Battle Droid</ITEMNAME>
        <CATEGORY>65</CATEGORY><ITEMYEAR>1999</ITEMYEAR></ITEM>
      <ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>3001</ITEMID>
        <ITEMNAME>Brick 2 x 4</ITEMNAME>
        <CATEGORY>5</CATEGORY><ITEMYEAR>1958</ITEMYEAR></ITEM>
    </CATALOG>"""
    r = ctx.post("/api/katalog/datei", content=xml.encode(),
                 headers={"Content-Type": "application/xml"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["neu"] == 2, d          # Set und Figur
    assert d["uebersprungen"] == 1   # das Teil
    with core.db() as conn:
        r2 = conn.execute(
            "SELECT img_url FROM katalog_index WHERE item_no = '10179-1'"
            " AND item_type = 'set'").fetchone()
    assert r2, "Das Set fehlt im Index"
    # Sets brauchen `SN`, nicht `MN`.
    assert r2["img_url"].endswith("/ItemImage/SN/0/10179-1.png"), r2["img_url"]


def test_kein_zweiter_name_fuer_die_bildadresse():
    """`_katalog_bild` gibt es weiter unten schon – eine ganz andere
    Funktion. Python nimmt die spätere Definition, und der Import legte
    daraufhin lautlos `None` in eine NOT-NULL-Spalte."""
    import re
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1]
              / "backend" / "main.py").read_text()
    for name in set(re.findall(r"^def (_\w+)\(", quelle, re.M)):
        n = len(re.findall(r"^def %s\(" % re.escape(name), quelle, re.M))
        assert n == 1, "%s ist %d-mal definiert" % (name, n)
