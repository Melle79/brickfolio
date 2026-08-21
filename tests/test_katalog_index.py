"""Ein eigener Abzug des BrickLink-Katalogs – damit die Suche das Aussehen
findet.

Der rote Protokolldroide heißt bei Rebrickable schlicht `R-3PO`: kein „rot",
kein „Protokolldroide", nichts zum Suchen. BrickLink nennt dieselbe Figur
„R-3PO Protocol Droid". Wer sie beschreibt statt sie zu benennen, findet sie
deshalb nur über einen eigenen Abzug – und der braucht kein Modell, das
irgendetwas weiß.

Gefüllt wird über die Nummern (`sw0001`, `sw0002`, …), weil BrickLink keine
Auflistung einer Kategorie anbietet (`items/MINIFIG?category_id=…` ist dort
kein gültiger Weg, geprüft am 21.08.2026).

**Gedrosselt**, und das ist keine Höflichkeit: Der BrickLink-Zugang ist
derselbe, über den die Preise laufen. Ein Durchlauf mit Vollgas könnte das
Tageskontingent aufbrauchen, und dann steht der Scanner ohne Preise da.
"""
import time

import pytest
import requests

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "kat.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('sven', 'x', 1, 1, ?)",
                     (now,))
    integrations._begriff_cache.clear()
    main._katalog_lauf.update({"aktiv": False, "nummer": 0, "gefunden": 0,
                               "neu": 0, "stop": False, "fehler": ""})
    monkeypatch.setattr(main, "KATALOG_TAKT", 0)      # Tests warten nicht
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def _bricklink(monkeypatch, katalog, gefragt=None):
    """BrickLink vortäuschen: {nummer: name}. Unbekannt = 404."""
    def fake(item_type, item_no):
        if gefragt is not None:
            gefragt.append(item_no)
        if item_no not in katalog:
            resp = requests.Response()
            resp.status_code = 404
            raise requests.HTTPError("404", response=resp)
        return {"name": katalog[item_no], "category_id": 65,
                "year_released": 2011}
    monkeypatch.setattr(integrations, "bricklink_item", fake)


# --------------------------------------------------------------- der Anbau

def test_der_abzug_laeuft_die_nummern_der_reihe_nach_ab(client, monkeypatch):
    gefragt: list = []
    _bricklink(monkeypatch, {"sw0001": "Darth Vader",
                             "sw0002": "R-3PO Protocol Droid"}, gefragt)
    main._katalog_anbau("sw")

    assert gefragt[:3] == ["sw0001", "sw0002", "sw0003"]
    d = client.get("/api/katalog/status").json()
    assert d["anzahl"] == 2 and d["laeuft"] is False


def test_eine_luecke_beendet_den_lauf_nicht(client, monkeypatch):
    """BrickLink vergibt Nummern, die es später nicht mehr gibt. Beim ersten
    404 abzubrechen hieße, mitten im Katalog stehen zu bleiben."""
    _bricklink(monkeypatch, {"sw0001": "Darth Vader", "sw0010": "R-3PO"})
    main._katalog_anbau("sw")

    with core.db() as conn:
        namen = [r["name"] for r in
                 conn.execute("SELECT name FROM katalog_index").fetchall()]
    assert sorted(namen) == ["Darth Vader", "R-3PO"]


def test_viele_luecken_am_stueck_beenden_ihn_doch(client, monkeypatch):
    """Sonst liefe er bis zur Notbremse bei 4.000 – eine Stunde für nichts."""
    gefragt: list = []
    _bricklink(monkeypatch, {"sw0001": "Darth Vader"}, gefragt)
    main._katalog_anbau("sw")
    assert len(gefragt) <= 1 + main.KATALOG_LUECKE + 1, len(gefragt)


def test_ein_abbruch_setzt_beim_naechsten_mal_fort(client, monkeypatch):
    """Zwanzig Minuten Arbeit dürfen nicht verfallen, nur weil jemand
    angehalten hat."""
    katalog = {"sw%04d" % i: "Figur %d" % i for i in range(1, 30)}
    gefragt: list = []
    _bricklink(monkeypatch, katalog, gefragt)

    def stoppen_nach_drei(item_type, item_no):
        if len(gefragt) >= 3:
            main._katalog_lauf["stop"] = True
        return {"name": katalog.get(item_no, ""), "category_id": 65,
                "year_released": 0}
    monkeypatch.setattr(integrations, "bricklink_item",
                        lambda t, n: (gefragt.append(n),
                                      stoppen_nach_drei(t, n))[1])
    main._katalog_anbau("sw")
    erste = len(gefragt)
    assert erste < 10, "der Stopp hat nicht gegriffen"

    main._katalog_lauf["stop"] = False
    main._katalog_anbau("sw")
    assert gefragt[erste] != "sw0001", "der zweite Lauf begann wieder bei eins"


def test_ein_anderer_fehler_beendet_den_lauf_sofort(client, monkeypatch):
    """401 heißt falscher Zugang, 429 heißt Kontingent erschöpft. Stur
    weiterzulaufen machte beides schlimmer."""
    gefragt: list = []

    def fake(item_type, item_no):
        gefragt.append(item_no)
        resp = requests.Response()
        resp.status_code = 429
        raise requests.HTTPError("429", response=resp)
    monkeypatch.setattr(integrations, "bricklink_item", fake)

    main._katalog_anbau("sw")
    assert len(gefragt) == 1, "es wurde nach dem 429 weitergefragt"
    assert "429" in main._katalog_lauf["fehler"]


def test_der_lauf_ist_gedrosselt():
    """Ohne Pause zwischen den Abrufen teilt sich der Anbau das
    Tageskontingent nicht mit den Preisen – er nimmt es."""
    import inspect
    quelle = inspect.getsource(main._katalog_anbau)
    assert "time.sleep(KATALOG_TAKT)" in quelle
    assert main.KATALOG_TAKT >= 0.5


# ------------------------------------------------------------- die Suche

def test_der_abzug_findet_was_rebrickable_nicht_hergibt(client, monkeypatch):
    """Der eigentliche Zweck: „Protocol Droid" findet R-3PO."""
    _bricklink(monkeypatch, {"sw0002": "R-3PO Protocol Droid"})
    main._katalog_anbau("sw")

    treffer = main._katalog_suchen("Protocol Droid")
    assert [t["name"] for t in treffer] == ["R-3PO Protocol Droid"]


def test_satzzeichen_zaehlen_auch_hier_nicht_mit(client, monkeypatch):
    """Dieselbe Elle wie in der Sammlung – „c3 po" findet `C-3PO`."""
    _bricklink(monkeypatch, {"sw0002": "C-3PO"})
    main._katalog_anbau("sw")
    assert main._katalog_suchen("c3 po")


def test_alle_woerter_muessen_vorkommen(client, monkeypatch):
    """Sonst zöge ein erfundener Begriff wie „Knight Hunter" jeden Ritter
    herein – genau der Fehler aus 2.28.1."""
    _bricklink(monkeypatch, {"sw0001": "Castle Knight"})
    main._katalog_anbau("sw")
    assert main._katalog_suchen("Knight")
    assert not main._katalog_suchen("Knight Hunter")


def test_die_katalogsuche_fragt_zuerst_den_eigenen_abzug(client, monkeypatch):
    """Er kostet nichts und kennt die beschreibenden Namen. Rebrickable erst
    danach – und nur, wenn nötig."""
    _bricklink(monkeypatch, {"sw0002": "R-3PO Protocol Droid"})
    main._katalog_anbau("sw")

    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": "test"})
    core.set_setting("rebrickable_key", "test-key")

    import json as json_mod

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content":
                                json_mod.dumps({"begriffe": ["Protocol Droid"]})}}
    monkeypatch.setattr(integrations.requests, "post",
                        lambda url, **kw: Fake())

    gefragt: list = []

    def nie(query, item_type="minifig", page=1, page_size=10):
        gefragt.append(query)
        return {"items": [], "count": 0}
    monkeypatch.setattr(integrations, "search_catalog", nie)

    d = client.get("/api/search/suggest?q=Protokolldroide").json()
    assert "R-3PO Protocol Droid" in [i["name"] for i in d["items"]]
    assert gefragt == [], "Rebrickable wurde trotz Treffer im Abzug gefragt"


# --------------------------------------------------------------- Bedienung

def test_ohne_bricklink_kein_start(client):
    r = client.post("/api/katalog/start")
    assert r.status_code == 400


def test_nur_fuer_admins(client):
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('gast', 'x', 0, 0, ?)",
                     (now,))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(2, "gast", False)
    assert c.get("/api/katalog/status").status_code in (401, 403)
    assert c.post("/api/katalog/start").status_code in (401, 403)


# ---------------------------------------------------- Mehrere Themen

def test_die_themen_laufen_nacheinander(client, monkeypatch):
    """Nicht nebeneinander: Alle Läufe teilen sich denselben
    BrickLink-Zugang. Zwei gleichzeitig hieße doppelter Takt – die
    Drosselung wäre ausgehebelt, für die es hier gute Gründe gibt."""
    reihenfolge: list = []

    def fake(item_type, item_no):
        reihenfolge.append(item_no[:3])
        resp = requests.Response()
        resp.status_code = 404
        raise requests.HTTPError("404", response=resp)
    monkeypatch.setattr(integrations, "bricklink_item", fake)

    main._katalog_reihe(["sw", "cty"])
    # Erst alle sw, dann alle cty – kein Wechsel mittendrin.
    assert reihenfolge == sorted(reihenfolge, key=lambda p: p != "sw")


def test_ein_kontingentfehler_stoppt_auch_die_folgenden_themen(client,
                                                               monkeypatch):
    """Der Zugang ist derselbe. Nach einem 429 beim ersten Thema hätte das
    zweite keine Chance – es würde das Problem nur verlängern."""
    gefragt: list = []

    def fake(item_type, item_no):
        gefragt.append(item_no)
        resp = requests.Response()
        resp.status_code = 429
        raise requests.HTTPError("429", response=resp)
    monkeypatch.setattr(integrations, "bricklink_item", fake)

    main._katalog_reihe(["sw", "cty", "njo"])
    assert len(gefragt) == 1, gefragt
    assert all(not n.startswith("cty") for n in gefragt)


def test_nur_buchstaben_als_praefix(client, monkeypatch):
    """Das Präfix wandert in eine Adresse – „../" hat dort nichts zu suchen."""
    core.set_setting("bl_consumer_key", "x")
    core.set_setting("bl_consumer_secret", "x")
    core.set_setting("bl_token", "x")
    core.set_setting("bl_token_secret", "x")
    r = client.post("/api/katalog/start", json={"themen": "../etc, sw0001, ?"})
    assert r.status_code == 400


def test_ohne_angabe_bleibt_es_bei_star_wars(client, monkeypatch):
    core.set_setting("bl_consumer_key", "x")
    core.set_setting("bl_consumer_secret", "x")
    core.set_setting("bl_token", "x")
    core.set_setting("bl_token_secret", "x")
    monkeypatch.setattr(main, "_katalog_reihe", lambda p: None)
    r = client.post("/api/katalog/start", json={})
    assert r.json()["themen"] == ["sw"]


# ------------------------------------------------------------ Bilder

def test_die_bildadresse_wird_mitgespeichert(client, monkeypatch):
    """Die Trefferkarten zeigen Bilder. Ohne Adresse käme ein Treffer aus
    dem Abzug als leeres graues Feld – und BrickLink liefert sie in
    derselben Antwort mit, es kostet also keinen zusätzlichen Abruf."""
    def fake(item_type, item_no):
        if item_no != "sw0002":
            resp = requests.Response()
            resp.status_code = 404
            raise requests.HTTPError("404", response=resp)
        return {"name": "R-3PO Protocol Droid", "category_id": 65,
                "year_released": 2011,
                "img_url": "https://img.bricklink.com/ML/sw0002.jpg"}
    monkeypatch.setattr(integrations, "bricklink_item", fake)
    main._katalog_anbau("sw")

    treffer = main._katalog_suchen("Protocol Droid")
    assert treffer[0]["img_url"] == "https://img.bricklink.com/ML/sw0002.jpg"


def test_alte_zeilen_bekommen_ihre_bildadresse_nachgetragen(client):
    """Zeilen aus einem Lauf vor 2.34.0 haben keine. Nachfüllen kostet
    keinen Abruf: Die Adresse folgt der Nummer, und der Bildserver
    unterscheidet nicht zwischen Groß- und Kleinschreibung."""
    with core.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " img_url, updated_at) VALUES ('sw0344', 'minifig', 'R-3PO', "
            "'r3po', '', 1)")
    core.init_db()          # idempotent, trägt nach
    with core.db() as conn:
        r = conn.execute("SELECT img_url FROM katalog_index WHERE "
                         "item_no = 'sw0344'").fetchone()
    assert r["img_url"] == "https://img.bricklink.com/ML/sw0344.jpg"


# ------------------------------------------------- Farben aus den Bildern

def _bild_und_farbe(monkeypatch, farben, gefragt=None, art=""):
    monkeypatch.setattr(integrations, "fetch_catalog_image",
                        lambda url, hosts=None: b"BILD")
    monkeypatch.setattr(integrations, "prepare_image",
                        lambda roh, seite=1200: roh)

    def fake(bild):
        if gefragt is not None:
            gefragt.append(bild)
        return {"art": art, "farben": list(farben)}
    monkeypatch.setattr(integrations, "bild_merkmale", fake)


def test_die_farbe_ergaenzt_was_im_namen_fehlt(client, monkeypatch):
    """Der eigentliche Zweck: „R-3PO Protocol Droid" sagt nirgends „rot".
    Erst mit der Farbe aus dem Bild findet „roter Protokolldroide" beides –
    die Art aus dem Namen, die Farbe aus dem Bild."""
    _bricklink(monkeypatch, {"sw0002": "R-3PO Protocol Droid"})
    main._katalog_anbau("sw")
    assert not main._katalog_suchen("red Protocol Droid")

    _bild_und_farbe(monkeypatch, ["red", "black"])
    main._katalog_farben()
    assert main._katalog_suchen("red Protocol Droid")


def test_die_art_der_figur_wird_mitgefragt(client, monkeypatch):
    """Erst nicht, dann doch: Mit `minicpm-v` lag die Art in zwei von drei
    Proben daneben, mit `qwen3-vl` an zehn echten Figuren zehnmal richtig
    (Stormtrooper → Soldat, Wookiee → Alien, R2-D2 → Droide). Sie ist
    genau das, was „roter Droide" braucht und in vielen Namen fehlt."""
    # Englisch gefragt: Der Index ist einsprachig, sonst treffen sich die
    # deutschen Merkmale und die englischen Suchbegriffe nie.
    assert set(integrations._BILD_SCHEMA["properties"]) == {"kind", "colors"}

    _bricklink(monkeypatch, {"sw0002": "Astromech Droid, R2-D2"})
    main._katalog_anbau("sw")
    _bild_und_farbe(monkeypatch, ["white", "blue"], art="droid")
    main._katalog_farben()
    assert main._katalog_suchen("droid")
    assert main._katalog_suchen("white droid")


def test_ein_leeres_ergebnis_wird_auch_festgehalten(client, monkeypatch):
    """Sonst versuchte der nächste Lauf dieselbe Figur wieder und käme nie
    ans Ende."""
    _bricklink(monkeypatch, {"sw0002": "C-3PO"})
    main._katalog_anbau("sw")
    gefragt: list = []
    _bild_und_farbe(monkeypatch, [], gefragt)

    main._katalog_farben()
    assert len(gefragt) == 1
    main._katalog_farben()
    assert len(gefragt) == 1, "dieselbe Figur wurde erneut angesehen"


def test_ohne_ki_kein_farblauf(client):
    r = client.post("/api/katalog/farben")
    assert r.status_code == 400


def test_die_merkmale_sind_englisch_wie_der_katalog(client, monkeypatch):
    """Der erste Anlauf legte sie deutsch ab („rot", „droide") und traf
    damit nie: Die Suchbegriffe kommen aus der Übersetzung und sind
    englisch. Selbst die rohe deutsche Frage scheiterte an der Beugung –
    „roter" ist nicht „rot". Einsprachig gibt es das Problem nicht."""
    assert "English" in integrations._BILD_FRAGE
    _bricklink(monkeypatch, {"sw0002": "R-3PO Protocol Droid"})
    main._katalog_anbau("sw")
    _bild_und_farbe(monkeypatch, ["red", "black"], art="droid")
    main._katalog_farben()

    # Genau der Weg aus dem Betrieb: deutsche Frage → englische Begriffe.
    assert main._katalog_suchen("Red Protocol Droid")
    # Und ein grauer darf dabei nicht mitkommen.
    assert not main._katalog_suchen("Gray Protocol Droid")
