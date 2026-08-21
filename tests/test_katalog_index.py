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

    # Vorn steht die Breitenerkennung – danach läuft er der Reihe nach.
    lauf = [n for n in gefragt if n.startswith("sw")]
    assert "sw0001" in lauf and "sw0002" in lauf
    assert lauf.index("sw0002") < lauf.index("sw0003")
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
    # Plus die Breitenerkennung vorweg (höchstens zehn Abrufe).
    assert len(gefragt) <= 10 + 1 + main.KATALOG_LUECKE + 1, len(gefragt)


def test_ein_abbruch_setzt_beim_naechsten_mal_fort(client, monkeypatch):
    """Zwanzig Minuten Arbeit dürfen nicht verfallen, nur weil jemand
    angehalten hat."""
    katalog = {"sw%04d" % i: "Figur %d" % i for i in range(1, 30)}
    gefragt: list = []
    _bricklink(monkeypatch, katalog, gefragt)

    def stoppen(item_type, item_no):
        # An der Nummer des **Laufs** aufhängen, nicht an der Zahl der
        # Abrufe: Die Breitenerkennung vorweg zählt sonst mit und der
        # Stopp feuert, bevor der Lauf überhaupt begonnen hat.
        if main._katalog_lauf["nummer"] >= 3:
            main._katalog_lauf["stop"] = True
        return {"name": katalog.get(item_no, ""), "category_id": 65,
                "year_released": 0}
    monkeypatch.setattr(integrations, "bricklink_item",
                        lambda t, n: (gefragt.append(n), stoppen(t, n))[1])
    main._katalog_anbau("sw")
    assert main._katalog_lauf["nummer"] < 15, "der Stopp hat nicht gegriffen"

    # Auch die Nummer zurücksetzen – sonst greift die Abbruchbedingung des
    # Tests sofort wieder, und man misst nur sich selbst.
    main._katalog_lauf["stop"] = False
    main._katalog_lauf["nummer"] = 0
    main._katalog_anbau("sw")
    # Der zweite Lauf beginnt mit der Breitenerkennung (niedrige Nummern),
    # zählt danach aber dort weiter, wo der erste aufhörte.
    with core.db() as conn:
        weiter = conn.execute("SELECT zuletzt FROM katalog_lauf WHERE "
                              "praefix = 'sw'").fetchone()["zuletzt"]
    assert weiter > 3, "der zweite Lauf begann wieder bei eins"


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
    # Einmal für die Breitenerkennung, einmal im Lauf – danach Schluss.
    assert len(gefragt) <= 2, "es wurde nach dem 429 weitergefragt: %s" % gefragt
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
    assert len(gefragt) <= 2, gefragt
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


def test_die_ziffernbreite_wird_erkannt(client, monkeypatch):
    """`sw0002` gibt es, `sw002` nicht – und die Burgfigur heißt `cas001`,
    nicht `cas0001`. Fest verdrahtete vier Ziffern ließen `cas`, `pi`, `hp`,
    `jw`, `sp`, `ww`, `lor` und `iaj` **komplett leer** ausgehen: Der Lauf
    meldete „fertig" nach fünfundzwanzig Fehlgriffen. Genau so ist es am
    21.08.2026 passiert."""
    _bricklink(monkeypatch, {"cas001": "Castle Knight",
                             "cas002": "Castle Wizard"})
    assert main._katalog_breite("cas") == 3
    main._katalog_anbau("cas")

    with core.db() as conn:
        namen = sorted(r["name"] for r in
                       conn.execute("SELECT name FROM katalog_index"))
    assert namen == ["Castle Knight", "Castle Wizard"]


def test_vier_ziffern_bleiben_vier(client, monkeypatch):
    _bricklink(monkeypatch, {"sw0001": "Darth Vader"})
    assert main._katalog_breite("sw") == 4


def test_ein_kontingentfehler_beendet_auch_die_breitenerkennung(
        client, monkeypatch):
    """Ein 429 als „gibt es nicht" zu lesen hieße, munter weiterzufragen –
    und das Kontingent ist ja gerade das Problem."""
    gefragt: list = []

    def fake(item_type, item_no):
        gefragt.append(item_no)
        resp = requests.Response()
        resp.status_code = 429
        raise requests.HTTPError("429", response=resp)
    monkeypatch.setattr(integrations, "bricklink_item", fake)

    main._katalog_breite("cas")
    assert len(gefragt) == 1, gefragt


# ----------------------------------------------------- Ein Präfix prüfen

def test_der_pruefknopf_nennt_praefix_und_breite(client, monkeypatch):
    """Ohne diese Auskunft trägt man ein Thema ein und wartet, bis der Lauf
    dort ankommt – bei vierzehn in der Warteschlange können das Stunden
    sein, und am Ende war es ein Tippfehler."""
    core.set_setting("bl_consumer_key", "x")
    core.set_setting("bl_consumer_secret", "x")
    core.set_setting("bl_token", "x")
    core.set_setting("bl_token_secret", "x")
    _bricklink(monkeypatch, {"cas001": "Castle Knight"})

    d = client.get("/api/katalog/pruefen?praefix=cas").json()
    assert d["gibt_es"] is True and d["breite"] == 3
    assert d["beispiel"] == "cas001" and d["name"] == "Castle Knight"


def test_ein_fantasiepraefix_wird_als_solches_gemeldet(client, monkeypatch):
    """`_katalog_breite` gibt im Zweifel 4 zurück – das heißt „nicht
    entschieden", nicht „gefunden". Ohne die zweite Prüfung meldete der
    Knopf jedes erfundene Präfix als gültig."""
    core.set_setting("bl_consumer_key", "x")
    core.set_setting("bl_consumer_secret", "x")
    core.set_setting("bl_token", "x")
    core.set_setting("bl_token_secret", "x")
    _bricklink(monkeypatch, {})

    d = client.get("/api/katalog/pruefen?praefix=xyz").json()
    assert d["gibt_es"] is False


def test_nur_buchstaben_beim_pruefen(client):
    assert client.get("/api/katalog/pruefen?praefix=../x").status_code == 400
    assert client.get("/api/katalog/pruefen?praefix=a").status_code == 400


# ------------------------------------------- Die Themenliste geht verloren

def test_nachgereichte_themen_landen_in_der_warteschlange(client, monkeypatch):
    """Sven trug bei Finns Instanz Themen nach – und sie waren weg.

    Lief schon ein Abzug, kam ein freundliches „läuft bereits" zurück und
    die neuen Themen wurden verworfen: kein Fehler, kein Hinweis, nichts.
    Bei einem Lauf über vierzehn Themen ist „warte, bis er durch ist" keine
    zumutbare Antwort – ein Abzug läuft hier Stunden.
    """
    core.set_setting("bl_consumer_key", "x")
    core.set_setting("bl_consumer_secret", "x")
    core.set_setting("bl_token", "x")
    core.set_setting("bl_token_secret", "x")
    main._katalog_lauf["aktiv"] = True
    main._katalog_lauf["praefix"] = "sw"
    main._katalog_lauf["warteschlange"] = ["cty"]
    try:
        d = client.post("/api/katalog/start",
                        json={"themen": "sw, cty, njo, cas"}).json()
        assert d["ergaenzt"] == ["njo", "cas"], "die Themen wurden verworfen"
        assert main._katalog_lauf["warteschlange"] == ["cty", "njo", "cas"]
    finally:
        main._katalog_lauf["aktiv"] = False
        main._katalog_lauf["warteschlange"] = []


def test_die_themenliste_ueberlebt_das_neuladen(client, monkeypatch):
    """Das Feld war nie eine Einstellung: Beim Öffnen wurde es aus der
    eingebauten Liste gefüllt, alles Eigene war beim nächsten Aufruf weg."""
    core.set_setting("bl_consumer_key", "x")
    core.set_setting("bl_consumer_secret", "x")
    core.set_setting("bl_token", "x")
    core.set_setting("bl_token_secret", "x")

    client.post("/api/katalog/themen", json={"themen": "sw, cty, adv"})
    assert client.get("/api/katalog/status").json()["themen"] == \
        ["sw", "cty", "adv"]


def test_ohne_eigene_liste_gilt_die_eingebaute(client):
    assert client.get("/api/katalog/status").json()["themen"] == \
        main.KATALOG_THEMEN


def test_doppelte_und_unsinnige_themen_fallen_raus(client):
    d = client.post("/api/katalog/themen",
                    json={"themen": "sw, SW , ../x, , cty"}).json()
    assert d["themen"] == ["sw", "cty"]


# ------------------------------ Ein Ausfall ist kein „nichts erkannt"

def _farbzeilen(anzahl=10):
    with core.db() as conn:
        for i in range(anzahl):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such,"
                " img_url, updated_at) VALUES (?, 'minifig', ?, ?,"
                " 'https://img.bricklink.com/ML/x.jpg', 0)",
                ("sw%04d" % i, "Figur %d" % i, "figur"))


def test_ein_ausfall_hakt_die_figur_nicht_als_angesehen_ab(client, monkeypatch):
    """Am 21.08.2026 antwortete Ollama nicht mehr – und der Farbenlauf hakte
    trotzdem eine Figur nach der anderen als erledigt ab. 45 waren so schon
    verbrannt: Sie stehen als „angesehen, nichts erkannt" in der Datenbank
    und kämen nie wieder an die Reihe.

    „Nichts erkannt" ist ein Ergebnis. „Gar nicht erst gefragt bekommen" ist
    ein Ausfall. Das darf nicht dasselbe sein.
    """
    _farbzeilen()
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda *a, **k: b"BILD")
    monkeypatch.setattr(main.integrations, "prepare_image",
                        lambda roh, n=512: roh)
    monkeypatch.setattr(main.integrations, "bild_merkmale",
                        lambda b: {"art": "", "farben": [],
                                   "fehler": "ReadTimeout: 120s"})
    monkeypatch.setattr(main, "KATALOG_FARB_TAKT", 0)

    main._katalog_farben()

    with core.db() as conn:
        offen = conn.execute("SELECT COUNT(*) AS n FROM katalog_index "
                             "WHERE farben = ''").fetchone()["n"]
    assert offen == 10, "der Ausfall wurde als Ergebnis verbucht"
    assert "antwortet nicht" in main._farb_lauf["fehler"]


def test_nach_fuenf_ausfaellen_ist_schluss(client, monkeypatch):
    """Sonst läuft er durch den ganzen Index – bei 7.000 Figuren wären das
    7.000 verbrannte Zeilen statt fünf verlorenen Versuchen."""
    _farbzeilen()
    versuche = []
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda *a, **k: b"BILD")
    monkeypatch.setattr(main.integrations, "prepare_image",
                        lambda roh, n=512: roh)

    def kaputt(b):
        versuche.append(1)
        return {"art": "", "farben": [], "fehler": "ReadTimeout"}
    monkeypatch.setattr(main.integrations, "bild_merkmale", kaputt)
    monkeypatch.setattr(main, "KATALOG_FARB_TAKT", 0)

    main._katalog_farben()
    assert len(versuche) == main.KATALOG_FARB_PATZER


def test_ein_fehlendes_bild_gilt_als_erledigt(client, monkeypatch):
    """BrickLink hat nicht zu jeder Figur ein Bild – `sw0307` (Embo) etwa
    liefert 404. Das ist ein Ergebnis: Sonst versuchte es jeder Lauf wieder
    und käme nie ans Ende."""
    _farbzeilen(3)

    def kein_bild(*a, **k):
        raise ValueError("404")
    monkeypatch.setattr(main.integrations, "fetch_catalog_image", kein_bild)
    monkeypatch.setattr(main, "KATALOG_FARB_TAKT", 0)

    main._katalog_farben()

    with core.db() as conn:
        offen = conn.execute("SELECT COUNT(*) AS n FROM katalog_index "
                             "WHERE farben = ''").fetchone()["n"]
    assert offen == 0
    assert main._farb_lauf["fehler"] == ""


def test_ein_einzelner_aussetzer_beendet_den_lauf_nicht(client, monkeypatch):
    """Das Modell wird gerade geladen – das kommt vor und darf keinen
    Abbruch auslösen. Erst fünf in Folge sind ein Ausfall."""
    _farbzeilen(6)
    n = {"i": 0}
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda *a, **k: b"BILD")
    monkeypatch.setattr(main.integrations, "prepare_image",
                        lambda roh, m=512: roh)

    def mal_so_mal_so(b):
        n["i"] += 1
        if n["i"] in (2, 5):
            return {"art": "", "farben": [], "fehler": "ReadTimeout"}
        return {"art": "droid", "farben": ["red"], "fehler": ""}
    monkeypatch.setattr(main.integrations, "bild_merkmale", mal_so_mal_so)
    monkeypatch.setattr(main, "KATALOG_FARB_TAKT", 0)

    main._katalog_farben()
    assert main._farb_lauf["fehler"] == ""
    with core.db() as conn:
        fertig = conn.execute("SELECT COUNT(*) AS n FROM katalog_index "
                              "WHERE farben <> ''").fetchone()["n"]
    assert fertig == 6, "die Aussetzer wurden nicht wiederholt"
