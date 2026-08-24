"""Wie der Abzug in eine Installation kommt.

Erzeugt wird er auf Svens NAS: Ein Dienst klappert BrickLink ab und lässt
ein Sehmodell die Katalogfotos beschreiben. Veröffentlicht wird davon
**nur die Nummer und die eigene Beschreibung** – Name, Jahr, Kategorie und
Bildadresse bleiben dort, denn das ist BrickLinks Inhalt, und dessen
Weitergabe an Dritte untersagen deren Nutzungsbedingungen.

Jede Installation zieht sich die Datei und schlägt die Namen über ihren
**eigenen** BrickLink-Zugang nach. Ohne den tut eine Installation ohnehin
nichts – deshalb kostet das niemanden etwas, was er nicht ohnehin hat.
"""
import json
import time

import pytest
import requests

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "kz.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('sven', 'x', 1, 1, ?)",
                     (now,))
    main._namen_lauf.update({"aktiv": False, "getan": 0, "stop": False,
                             "fehler": ""})
    monkeypatch.setattr(main, "KATALOG_NAMEN_TAKT", 0)
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def _datei(monkeypatch, zeilen, etag='"abc"', status=200, kopf=None):
    inhalt = "\n".join(json.dumps(z) for z in zeilen) + "\n"

    # `text` als schlichtes Klassenmerkmal, nicht als Eigenschaft: Eine
    # Methode namens `text`, die `text` zurückgeben will, findet sich selbst.
    class Fake:
        status_code = status
        headers = kopf if kopf is not None else ({"ETag": etag} if etag else {})
        content = inhalt.encode()
        text = inhalt

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(str(self.status_code))

    monkeypatch.setattr(main.requests, "get", lambda url, **kw: Fake())


def test_der_abzug_kommt_als_datei_an(client, monkeypatch):
    _datei(monkeypatch, [
        {"item_no": "cas001", "art": "knight", "farben": "red, blue",
         "merkmale": "cape yellow green dragon", "modell": "qwen3-vl:latest"}])

    erg = main._katalog_ziehen()
    assert erg["neu"] == 1
    with core.db() as conn:
        r = conn.execute("SELECT * FROM katalog_index").fetchone()
    assert r["merkmale"] == "cape yellow green dragon"
    assert r["art"] == "knight"
    # Der Name steht **nicht** in der Datei – den holt die Installation selbst.
    assert r["name"] == ""


def test_ein_unveraenderter_stand_kostet_fast_nichts(client, monkeypatch):
    """3,3 MB alle zwölf Stunden zu ziehen, obwohl sich nichts geändert hat,
    wäre Verschwendung – auf beiden Seiten."""
    core.set_setting("katalog_etag", '"abc"')
    gefragt = {}

    class Fake:
        status_code = 304
        headers = {}

        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        gefragt.update(kw.get("headers") or {})
        return Fake()
    monkeypatch.setattr(main.requests, "get", fake_get)

    assert main._katalog_ziehen()["grund"] == "unverändert"
    assert gefragt.get("If-None-Match") == '"abc"'


def test_eine_kaputte_zeile_wirft_nicht_alles_weg(client, monkeypatch):
    class Fake:
        status_code = 200
        headers = {}
        content = b"x"
        text = ('{"item_no": "a001", "merkmale": "torso red"}\n'
                'das ist kein JSON\n'
                '{"item_no": "a002", "merkmale": "torso blue"}\n')

        def raise_for_status(self):
            pass
    monkeypatch.setattr(main.requests, "get", lambda url, **kw: Fake())

    assert main._katalog_ziehen()["neu"] == 2


def test_der_name_wird_beim_ziehen_nicht_ueberschrieben(client, monkeypatch):
    """Sonst wäre die Arbeit des Namenslaufs bei jedem Abruf wieder weg."""
    _datei(monkeypatch, [{"item_no": "cas001", "merkmale": "torso red"}])
    main._katalog_ziehen()
    with core.db() as conn:
        conn.execute("UPDATE katalog_index SET name = 'Dragon Master', "
                     "such = 'dragonmaster' WHERE item_no = 'cas001'")

    _datei(monkeypatch, [{"item_no": "cas001", "merkmale": "torso red blue"}],
           etag=None)
    main._katalog_ziehen()
    with core.db() as conn:
        r = conn.execute("SELECT name, such, merkmale FROM katalog_index"
                         " WHERE item_no = 'cas001'").fetchone()
    assert r["name"] == "Dragon Master" and r["such"] == "dragonmaster"
    assert r["merkmale"] == "torso red blue", "die Beschreibung kam nicht an"


def test_eine_zu_grosse_datei_wird_abgewiesen(client, monkeypatch):
    """Die Adresse lässt sich verstellen – ohne Deckel zöge die Instanz
    sich alles, was dort liegt."""
    class Fake:
        status_code = 200
        headers = {}
        content = b"x" * (main.KATALOG_MAX_BYTES + 1)
        text = ""

        def raise_for_status(self):
            pass
    monkeypatch.setattr(main.requests, "get", lambda url, **kw: Fake())

    with pytest.raises(ValueError):
        main._katalog_ziehen()


# ------------------------------------------- Namen über den eigenen Zugang

def _bricklink(monkeypatch, katalog):
    def fake(item_type, item_no):
        if item_no not in katalog:
            resp = requests.Response()
            resp.status_code = 404
            raise requests.HTTPError("404", response=resp)
        return {"name": katalog[item_no], "year_released": 1993,
                "category_id": 53}
    monkeypatch.setattr(integrations, "bricklink_item", fake)
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)


def test_die_namen_kommen_ueber_den_eigenen_zugang(client, monkeypatch):
    _datei(monkeypatch, [{"item_no": "cas001", "merkmale": "torso red"}])
    main._katalog_ziehen()
    _bricklink(monkeypatch, {"cas001": "Dragon Master - Yellow Plumes"})

    assert main._katalog_namen()["getan"] == 1
    with core.db() as conn:
        r = conn.execute("SELECT name, such, jahr FROM katalog_index").fetchone()
    assert r["name"] == "Dragon Master - Yellow Plumes"
    # Der Suchtext muss dieselbe Elle haben wie die Suche: zusammengezogen,
    # ohne Satzzeichen. Sonst findet der Vorfilter nichts.
    assert r["such"] == "dragonmasteryellowplumes"
    assert r["jahr"] == 1993


def test_eine_verschwundene_nummer_haelt_den_lauf_nicht_auf(client, monkeypatch):
    """Ohne Strich griffe jeder Lauf wieder nach derselben Zeile und käme
    nie über sie hinaus."""
    _datei(monkeypatch, [{"item_no": "weg001", "merkmale": "torso red"}])
    main._katalog_ziehen()
    _bricklink(monkeypatch, {})

    main._katalog_namen()
    with core.db() as conn:
        r = conn.execute("SELECT name FROM katalog_index").fetchone()
    assert r["name"] == "–"
    assert main._katalog_namen()["getan"] == 0


def test_ein_kontingentfehler_beendet_den_namenslauf(client, monkeypatch):
    """401 und 429 gelten für alle folgenden mit – der Zugang ist derselbe.
    Weiterzulaufen machte beides schlimmer."""
    _datei(monkeypatch, [{"item_no": "a%03d" % i, "merkmale": "torso red"}
                         for i in range(5)])
    main._katalog_ziehen()

    versuche = []

    def kontingent(item_type, item_no):
        versuche.append(item_no)
        resp = requests.Response()
        resp.status_code = 429
        raise requests.HTTPError("429", response=resp)
    monkeypatch.setattr(integrations, "bricklink_item", kontingent)
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)

    erg = main._katalog_namen()
    assert len(versuche) == 1, "er lief weiter, obwohl das Kontingent leer war"
    assert "429" in erg["fehler"]


def test_ohne_bricklink_passiert_nichts(client, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: False)
    assert main._katalog_namen()["getan"] == 0


def test_der_stand_nennt_die_fehlenden_namen(client, monkeypatch):
    """Sie fehlen am Anfang **allen** – das gehört gesagt, sonst hält man es
    für einen Fehler."""
    _datei(monkeypatch, [{"item_no": "a001", "merkmale": "torso red"},
                         {"item_no": "a002", "merkmale": "torso blue"}])
    main._katalog_ziehen()

    d = client.get("/api/katalog/stand").json()
    assert d["figuren"] == 2 and d["beschrieben"] == 2
    assert d["ohne_namen"] == 2


# --------------------------------------------------- Der Abzug ist optional

def test_abgeschaltet_wird_nichts_geholt(client, monkeypatch):
    """Er kostet etwas: 3,3 MB alle zwölf Stunden und beim ersten Mal rund
    9.700 BrickLink-Abrufe für die Namen. Wer die Suche nach dem Aussehen
    nicht braucht, soll das nicht zahlen müssen."""
    gefragt = []
    monkeypatch.setattr(main.requests, "get",
                        lambda url, **kw: gefragt.append(url))
    core.set_setting("katalog_aus", "1")

    assert main._katalog_ziehen()["grund"] == "abgeschaltet"
    assert main._katalog_namen()["grund"] == "abgeschaltet"
    assert gefragt == [], "es wurde trotzdem geholt"


def test_der_schalter_laesst_den_bestand_liegen(client, monkeypatch):
    """Abgeschaltet bleibt das Geholte liegen – es stört nicht und wäre
    beim Wiedereinschalten sonst noch einmal zu holen."""
    _datei(monkeypatch, [{"item_no": "a001", "merkmale": "torso red"}])
    main._katalog_ziehen()

    client.post("/api/katalog/aktiv", json={"aktiv": False})
    d = client.get("/api/katalog/stand").json()
    assert d["aktiv"] is False and d["figuren"] == 1


def test_wieder_eingeschaltet_holt_er_von_selbst(client, monkeypatch):
    _datei(monkeypatch, [{"item_no": "a001", "merkmale": "torso red"}])
    core.set_setting("katalog_aus", "1")

    r = client.post("/api/katalog/aktiv", json={"aktiv": True}).json()
    assert r["aktiv"] is True
    assert core.get_setting("katalog_aus") == ""


# ------------------------------------- Die Katalogdatei selbst einlesen

XML_PROBE = """<?xml version="1.0" encoding="UTF-8"?>
<CATALOG>
  <ITEM><ITEMTYPE>M</ITEMTYPE><ITEMID>sw0344</ITEMID>
    <ITEMNAME>R-3PO Protocol Droid</ITEMNAME><CATEGORY>65</CATEGORY>
    <ITEMYEAR>2011</ITEMYEAR></ITEM>
  <ITEM><ITEMTYPE>M</ITEMTYPE><ITEMID>cas001</ITEMID>
    <ITEMNAME>Dragon Master</ITEMNAME><CATEGORY>53</CATEGORY>
    <ITEMYEAR>1993</ITEMYEAR></ITEM>
</CATALOG>"""


def test_die_katalogdatei_bringt_die_namen_in_sekunden(client):
    """Der veröffentlichte Index enthält bewusst keine Namen – die sind
    BrickLinks Inhalt. Bisher holte jede Installation sie über die API:
    rund 9.700 Abrufe über gut drei Tage. Dieselben Namen stehen in einer
    Datei, die BrickLink jedem Mitglied zum Herunterladen anbietet."""
    d = client.post("/api/katalog/datei", content=XML_PROBE).json()
    assert d["neu"] == 2 and d["gesamt"] == 2
    with core.db() as conn:
        r = conn.execute("SELECT name, such, jahr FROM katalog_index "
                         "WHERE item_no = 'sw0344'").fetchone()
    assert r["name"] == "R-3PO Protocol Droid"
    assert r["such"] == "r3poprotocoldroid"
    assert r["jahr"] == 2011
    # Und danach findet die Suche sie über den Namen.
    assert main._katalog_suchen("Protocol Droid")


def test_die_beschreibung_ueberlebt_den_import(client):
    """Was das Sehmodell einmal beschrieben hat, bleibt – sonst wäre die
    teuerste Arbeit im ganzen Ablauf mit einem Klick weg."""
    _datei_import = XML_PROBE
    with core.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " merkmale, updated_at) VALUES ('sw0344', 'minifig', '', '',"
            " 'torso red black chest panel', 1)")
    client.post("/api/katalog/datei", content=_datei_import)
    with core.db() as conn:
        r = conn.execute("SELECT name, merkmale FROM katalog_index "
                         "WHERE item_no = 'sw0344'").fetchone()
    assert r["merkmale"] == "torso red black chest panel"
    assert r["name"] == "R-3PO Protocol Droid"


def test_eine_zu_grosse_datei_wird_abgewiesen(client):
    """Ohne Deckel legt ein Fehlgriff den Container lahm."""
    r = client.post("/api/katalog/datei",
                    content=b"x" * (main.KATALOG_DATEI_MAX + 1))
    assert r.status_code == 413


def test_unlesbares_xml_gibt_einen_klaren_fehler(client):
    r = client.post("/api/katalog/datei", content="kein XML")
    assert r.status_code == 400 and "XML" in r.json()["detail"]


def test_die_suche_gilt_als_eingerichtet_wenn_der_abzug_etwas_hat(client):
    """Die Oberfläche zeigte „Katalogsuche ist nicht eingerichtet", **bevor**
    sie den Server fragte – das Kennzeichen hing allein an Rebrickable."""
    core.set_setting("rebrickable_key", "")
    assert client.get("/api/config").json()["catalog_search"] is False
    client.post("/api/katalog/datei", content=XML_PROBE)
    assert client.get("/api/config").json()["catalog_search"] is True


XML_TEILE = """<?xml version="1.0" encoding="UTF-8"?>
<CATALOG>
  <ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>3001</ITEMID>
    <ITEMNAME>Brick 2 x 4</ITEMNAME><CATEGORY>5</CATEGORY></ITEM>
  <ITEM><ITEMTYPE>S</ITEMTYPE><ITEMID>7140-1</ITEMID>
    <ITEMNAME>X-wing Fighter</ITEMNAME><CATEGORY>65</CATEGORY></ITEM>
</CATALOG>"""


def test_eine_teiledatei_landet_nicht_im_figurenabzug(client):
    """Am 24.08.2026 hat Sven `Parts.xml` eingelesen – und 118.000 Steine
    standen als Minifiguren im Abzug: 137.156 Zeilen statt 19.158. Die
    Artikelart steht in der Datei; sie zu ignorieren war der Fehler."""
    r = client.post("/api/katalog/datei", content=XML_TEILE)
    assert r.status_code == 400
    assert "Minifiguren" in r.json()["detail"]
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM "
                            "katalog_index").fetchone()["n"] == 0


def test_gemischte_datei_nimmt_nur_die_figuren(client):
    gemischt = XML_PROBE.replace("</CATALOG>", """
  <ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>3001</ITEMID>
    <ITEMNAME>Brick 2 x 4</ITEMNAME></ITEM>
</CATALOG>""")
    d = client.post("/api/katalog/datei", content=gemischt).json()
    assert d["neu"] == 2 and d["uebersprungen"] == 1
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM katalog_index "
                            "WHERE item_no = '3001'").fetchone()["n"] == 0


def test_kein_501_wenn_der_abzug_gefuellt_ist(client):
    """„roter droide" findet im englischen Abzug nichts – das ist „nichts
    gefunden", nicht „nicht eingerichtet". Der Unterschied ist der zwischen
    einem Hinweis, der stimmt, und einem, der in die Irre führt."""
    core.set_setting("rebrickable_key", "")
    client.post("/api/katalog/datei", content=XML_PROBE)
    r = client.get("/api/search?q=roter%20droide")
    assert r.status_code == 200 and r.json()["items"] == []
