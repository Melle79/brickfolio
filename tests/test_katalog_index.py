"""Ein eigener Abzug des BrickLink-Katalogs – damit die Suche das Aussehen
findet.

Der rote Protokolldroide heißt bei Rebrickable schlicht `R-3PO`: kein „rot",
kein „Protokolldroide", nichts zum Suchen. BrickLink nennt dieselbe Figur
„R-3PO Protocol Droid", und das Bild zeigt einen schwarzen Aufdruck auf rotem
Torso. Wer sie beschreibt statt sie zu benennen, findet sie deshalb nur über
einen eigenen Abzug – und der braucht kein Modell, das irgendetwas weiß.

**Erzeugt wird er seit 2.41.0 nicht mehr hier.** Bis dahin klapperte jede
Instanz BrickLink selbst ab und ließ ein eigenes Sehmodell die Bilder
beschreiben – viermal dieselbe Arbeit für dasselbe Ergebnis, denn der Abzug
beschreibt BrickLinks Fotos, nicht die Sammlung von irgendwem. Und jede
brauchte dafür eigene BrickLink-Zugangsdaten und ein Sehmodell; drei von vier
hatten seit dem 23.08.2026 keines mehr und deshalb null Zeilen.

Was hier geprüft wird, ist der Rest, und der ist das Wertvolle: der lokale
Abzug in `katalog_index` und die Suche darin. Wie er hineinkommt, steht in
`test_katalog_hub.py`; wie er entsteht, im Hub-Repo.
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
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def _zeile(item_no, name, merkmale="", farben="", art="", item_type="minifig"):
    """Eine Zeile so ablegen, wie der Hub sie liefert."""
    with core.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " img_url, farben, art, merkmale, jahr, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 2011, 1)",
            # Dieselbe Elle wie beim Eintragen: Der Name zusammengezogen,
            # ohne Satzzeichen. Der Vorfilter sucht mit `LIKE '%c3%'`, und
            # mit Leerzeichen („c 3po") fände er nichts.
            (item_no, item_type, name, main._wortanfaenge(name)[0],
             "https://img.bricklink.com/ML/%s.jpg" % item_no,
             farben, art, merkmale))


# ------------------------------------------------------------- die Suche

def test_der_abzug_findet_was_rebrickable_nicht_hergibt(client):
    """Der eigentliche Zweck: „Protocol Droid" findet R-3PO."""
    _zeile("sw0002", "R-3PO Protocol Droid")
    treffer = main._katalog_suchen("Protocol Droid")
    assert [t["name"] for t in treffer] == ["R-3PO Protocol Droid"]


def test_satzzeichen_zaehlen_auch_hier_nicht_mit(client):
    """Dieselbe Elle wie in der Sammlung – „c3 po" findet `C-3PO`."""
    _zeile("sw0002", "C-3PO")
    assert main._katalog_suchen("c3 po")


def test_alle_woerter_muessen_vorkommen(client):
    """Sonst zöge ein erfundener Begriff wie „Knight Hunter" jeden Ritter
    herein – genau der Fehler aus 2.28.1."""
    _zeile("cas001", "Castle Knight")
    assert main._katalog_suchen("Knight")
    assert not main._katalog_suchen("Knight Hunter")


def test_der_aufdruck_ist_durchsuchbar(client):
    """Svens Ziel vom 21.08.2026: „welche Farbe hat der Torso, der Kopf, die
    Haare, der Helm. Welche farbe haben die bedruckungen".

    Vorher standen im Index Art und bis zu drei Farben. Damit fand „roter
    Droide" zwar etwas – „roter Droide mit schwarzem Aufdruck" aber nicht,
    weil der Aufdruck im Suchtext gar nicht vorkam.
    """
    _zeile("sw0344", "R-3PO Protocol Droid", farben="red, black", art="droid",
           merkmale="head red simple face; torso red black chest panel")
    assert main._katalog_suchen("red droid")
    assert main._katalog_suchen("black chest panel")
    assert main._katalog_suchen("red droid black panel"), \
        "der Aufdruck ist nicht durchsuchbar"


def test_ein_anderer_droide_faellt_dabei_heraus(client):
    """Die Probe aufs Exempel: Nur der mit schwarzem Aufdruck, nicht jeder
    rote Droide."""
    _zeile("sw0344", "R-3PO Protocol Droid", farben="red, black", art="droid",
           merkmale="torso red black chest panel")
    _zeile("sw0003", "R2-D2 Astromech Droid", farben="white, blue",
           art="droid", merkmale="torso white blue panel")

    treffer = [x["item_id"] for x in main._katalog_suchen("red droid black")]
    assert treffer == ["sw0344"], treffer


def test_bei_typ_set_kommt_keine_figur(client):
    """Svens Fall vom 21.08.2026: Oben stand „Set", gesucht war die UCS Razor
    Crest – heraus kam „Clone ARF Trooper Razor", eine Figur. Der Index
    enthält ausschließlich Figuren, wurde aber ohne Rücksicht auf den
    eingestellten Typ befragt."""
    _zeile("sw0297", "Clone ARF Trooper Razor")
    assert main._katalog_suchen("Razor", item_type="minifig")
    assert not main._katalog_suchen("Razor", item_type="set")


def test_die_katalogsuche_fragt_zuerst_den_eigenen_abzug(client, monkeypatch):
    """Er kostet nichts und kennt die beschreibenden Namen. Rebrickable erst
    danach – und nur, wenn nötig."""
    _zeile("sw0002", "R-3PO Protocol Droid")
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


# ------------------------------------------- Erzeugt wird hier nichts mehr

def test_die_steuerung_ist_verschwunden(client):
    """Abzug starten, anhalten, Themen, Prüfknopf, Bilderlauf – alles weg.

    Nicht Kosmetik: Solange die Endpunkte da sind, klappert jede Instanz
    weiter BrickLink ab, wenn jemand sie aufruft – mit demselben Kontingent,
    das die Preise brauchen.
    """
    for pfad in ("/api/katalog/start", "/api/katalog/stop",
                 "/api/katalog/farben", "/api/katalog/farben/stop",
                 "/api/katalog/themen"):
        assert client.post(pfad).status_code == 404, pfad
    for pfad in ("/api/katalog/status", "/api/katalog/pruefen?praefix=sw"):
        assert client.get(pfad).status_code == 404, pfad


def test_der_stand_sagt_was_angekommen_ist(client):
    """Das Einzige, was bleibt – und ohne das sähe man erst zwölf Stunden
    später am Protokoll, ob überhaupt etwas ankommt."""
    _zeile("sw0002", "R-3PO Protocol Droid", merkmale="torso red")
    _zeile("sw0003", "R2-D2")
    core.set_setting("katalog_geholt_at", "1000")

    d = client.get("/api/katalog/stand").json()
    assert d["figuren"] == 2 and d["beschrieben"] == 1
    assert d["geholt_at"] == 1000
    # Beide Zeilen haben hier einen Namen – im echten Betrieb fehlt er am
    # Anfang allen, weil die veröffentlichte Datei ihn nicht enthält.
    assert d["ohne_namen"] == 0


def test_der_eigene_abzug_braucht_kein_rebrickable(client, monkeypatch):
    """Pauls Instanz am 24.08.2026: BrickLink eingerichtet, 19.158 Figuren
    mit Beschreibung im Abzug – und die Suche gab eine leere Liste zurück,
    weil der **Rebrickable**-Schlüssel fehlte. Der Abzug liegt lokal; er
    braucht davon nichts.

    Rebrickable ist erst der zweite Versuch, wenn der eigene nichts hergibt.
    """
    _zeile("sw0344", "R-3PO Protocol Droid", farben="red, black",
           merkmale="torso red black chest panel")
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": "test"})
    # Ausdrücklich **kein** Rebrickable-Schlüssel.
    core.set_setting("rebrickable_key", "")

    import json as json_mod

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content":
                                json_mod.dumps({"begriffe": ["red droid"]})}}
    monkeypatch.setattr(integrations.requests, "post",
                        lambda url, **kw: Fake())

    d = client.get("/api/search/suggest?q=roter%20Droide").json()
    assert [i["item_id"] for i in d["items"]] == ["sw0344"], d


def test_die_hauptsuche_fragt_zuerst_den_eigenen_abzug(client, monkeypatch):
    """Sie stieg mit einem 501 aus, wenn kein Rebrickable-Schlüssel
    hinterlegt war – der eigene Abzug wurde **gar nicht** befragt. Auf
    Pauls Instanz lagen dabei 19.158 Figuren mit Namen und Beschreibung,
    und jede Suche im manuellen Erfassen blieb stumm (24.08.2026)."""
    _zeile("sw0344", "R-3PO Protocol Droid", merkmale="torso red")
    core.set_setting("rebrickable_key", "")

    d = client.get("/api/search?q=Protocol%20Droid").json()
    assert [i["item_id"] for i in d["items"]] == ["sw0344"]


def test_ein_ausfall_bei_rebrickable_wirft_den_eigenen_nicht_weg(client,
                                                                monkeypatch):
    """Vorher endete die Suche mit einem Fehler, obwohl die Antwort längst
    dalag."""
    _zeile("sw0344", "R-3PO Protocol Droid", merkmale="torso red")
    core.set_setting("rebrickable_key", "test-key")

    def kaputt(*a, **k):
        raise requests.RequestException("weg")
    monkeypatch.setattr(integrations, "search_catalog", kaputt)

    d = client.get("/api/search?q=Protocol%20Droid").json()
    assert [i["item_id"] for i in d["items"]] == ["sw0344"]


def test_ohne_abzug_und_ohne_rebrickable_bleibt_der_hinweis(client):
    """Sonst sähe „nichts eingerichtet" aus wie „nichts gefunden"."""
    core.set_setting("rebrickable_key", "")
    assert client.get("/api/search?q=Droide").status_code == 501


# ------------------------------------------------- Gröbere Farben als Rückfall

def test_goldener_ritter_findet_die_gelb_gesehene_figur(client):
    """Das Sehmodell nennt Gold „yellow" – gemessen an 17.286 Figuren sagt
    es bei „Gold" im Namen 152-mal „yellow", bei „Tan" 714-mal. Dadurch
    waren rund 1.900 Figuren über ihre tatsächliche Farbe nicht auffindbar
    (25.08.2026)."""
    _zeile("cas100", "Royal Knight", farben="yellow, red",
           merkmale="helmet yellow crown; torso red lion")
    assert [t["item_id"] for t in main._katalog_suchen("gold knight")] \
        == ["cas100"]


def test_der_genaue_treffer_kommt_zuerst(client):
    """Der zweite Versuch hängt an, er drängt sich nicht vor."""
    _zeile("cas101", "Gold Knight", farben="gold, red")
    _zeile("cas102", "Yellow Knight", farben="yellow, red")
    assert [t["item_id"] for t in main._katalog_suchen("gold knight")] \
        == ["cas101", "cas102"]


def test_gelb_weicht_nicht_auf_gold_aus(client):
    """Einseitig mit Absicht: `yellow` trifft ohnehin tausende Figuren.
    Eine Verwandtschaft dorthin machte die Suche nur breiter."""
    _zeile("cas103", "Gold Knight", farben="gold, red")
    assert main._katalog_suchen("yellow knight") == []


def test_ohne_farbe_im_begriff_gibt_es_keinen_zweiten_versuch(client, monkeypatch):
    """Sonst liefe jede erfolglose Suche zweimal."""
    laeufe = []
    echt = main._katalog_lauf_suchen
    monkeypatch.setattr(main, "_katalog_lauf_suchen",
                        lambda b, *a, **k: laeufe.append(b) or echt(b, *a, **k))
    main._katalog_suchen("Protocol Droid")
    assert laeufe == ["Protocol Droid"]


# --------------------------------- Schonender Bildmodus, benutzereigen

def test_der_schonende_modus_folgt_dem_benutzer(client):
    """Er lag allein im `localStorage` – und der gehört zur Adresse, nicht
    zum Gerät. Sven hatte ihn eingeschaltet, und der Renderer stürzte
    trotzdem ab: Die abgestürzte Sitzung lief über `http://…:8300`, die
    eingeschaltete über HTTPS. Zwei Adressen, zwei Speicher (25.08.2026)."""
    assert client.get("/api/config").json()["schonend"] is None
    assert client.post("/api/settings/schonend",
                       json={"schonend": True}).status_code == 200
    assert client.get("/api/config").json()["schonend"] is True
    client.post("/api/settings/schonend", json={"schonend": False})
    assert client.get("/api/config").json()["schonend"] is False


def test_nie_gesetzt_ist_nicht_dasselbe_wie_aus(client):
    """Sonst schaltete das erste Laden nach dem Update jedem den Modus ab,
    der ihn lokal längst anhatte – und der Schutz wäre weg, ohne dass
    jemand etwas angefasst hätte."""
    assert client.get("/api/config").json()["schonend"] is None


def test_jeder_benutzer_hat_seinen_eigenen(client):
    """Es ist eine Eigenschaft des Geräts, nicht der Instanz."""
    client.post("/api/settings/schonend", json={"schonend": True})
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('zweiter', 'x', 0, 0, 1)")
    d = client.get("/api/config", headers={
        "Authorization": "Bearer " + core.create_token(2, "zweiter", False)}).json()
    assert d["schonend"] is None


# ------------------------------------- Breitere Begriffe verdrängen nicht

def test_droid_kommt_hinter_red_droid(client):
    """„roter droide" ergibt `Red Droid` **und** `Droid`. Der zweite ist eine
    Teilmenge: Alles, was er zusätzlich findet, erfüllt die Farbe nicht. In
    einer echten Suche standen dadurch R2-D2 und ein Pit Droid mit braunen
    Armen auf Platz 3 und 4 (28.08.2026)."""
    paare = [("Red Droid", ["a"]), ("Droid", ["a", "b", "c"])]
    eng, weit = main._teilmengen_teilen(paare)
    assert eng == [("Red Droid", ["a"])]
    assert weit == [("Droid", ["a", "b", "c"])]


def test_der_weitere_bleibt_wenn_der_engere_nichts_findet(client):
    """Sonst gäbe es gar kein Ergebnis."""
    paare = [("Red Droid", []), ("Droid", ["a", "b"])]
    eng, weit = main._teilmengen_teilen(paare)
    assert eng == paare and weit == []


def test_unabhaengige_begriffe_bleiben_zusammen(client):
    """`Knight` und `Squire` sind keine Teilmengen voneinander."""
    paare = [("Knight", ["a"]), ("Squire", ["b"])]
    eng, weit = main._teilmengen_teilen(paare)
    assert eng == paare and weit == []


# --------------------- Farben müssen die Figur beschreiben, nicht ein Detail

def test_ein_rotes_detail_macht_keinen_roten_droiden(client):
    """Der Droideka (`sw0063`) ist braun und grau. Seine Beschreibung sagt
    „head light gray cylindrical with red and white sections" – ein rotes
    Detail am Kopf. Damit stand er unter den roten Droiden (28.08.2026)."""
    _zeile("sw0063", "Droideka (Destroyer Droid) - Brown, Light Gray",
           farben="light, gray, brown",
           merkmale="head light gray cylindrical with red and white sections")
    assert main._katalog_suchen("Red Droid") == []


def test_die_farbe_im_namen_zaehlt(client):
    """`Battle Droid - Sand Red` hat `farben=tan`. Die Farbliste allein
    wäre zu streng – der Name ist Katalogwahrheit."""
    _zeile("sw0061", "Battle Droid - Sand Red (Geonosian)", farben="tan",
           merkmale="head tan; torso tan")
    assert [t["item_id"] for t in main._katalog_suchen("Red Droid")] == ["sw0061"]


def test_die_farbliste_zaehlt_auch(client):
    """`Pit Droid (Sebulba's)` trägt die Farbe nicht im Namen, wohl aber in
    der Zusammenfassung des Sehmodells."""
    _zeile("sw0064", "Pit Droid (Sebulba's)", farben="dark, red, white",
           merkmale="head white; torso dark red")
    assert [t["item_id"] for t in main._katalog_suchen("Red Droid")] == ["sw0064"]


def test_ohne_farbe_im_begriff_aendert_sich_nichts(client):
    """`Knight` ist kein Farbwort – die Prüfung darf nicht zuschlagen."""
    _zeile("cas001", "Dragon Master", farben="yellow",
           merkmale="helmet black knight crest")
    assert main._katalog_suchen("Knight")


def test_der_weitere_begriff_kommt_nur_bei_duerftiger_ausbeute(client, monkeypatch):
    """„roter droide" fand sechs rote und hängte danach jeden weiteren
    Droiden an – Droideka „Copper Top", R7-A7, Sentry Droid. Der Rückfall
    stand auf `SUGGEST_MAX` (200) und lief damit praktisch immer. Wer eine
    Farbe eingibt, will nicht die Liste ohne Farbe hinterher (28.08.2026)."""
    for i in range(6):
        _zeile("sw%03d" % i, "Red Droid %d" % i, farben="red")
    _zeile("sw900", "Sentry Droid", farben="white")
    # Ohne Ollama liefert `suchbegriffe` nichts, und der Test prüfte eine
    # leere Liste – er lief auch ohne die Änderung durch. Die Übersetzung
    # wird deshalb vorgegeben.
    monkeypatch.setattr(integrations, "suchbegriffe",
                        lambda q: ["Red Droid", "Droid"])
    core.set_setting("ollama_url", "http://x")
    assert len(main._katalog_suchen("Red Droid")) == 6
    d = main.suggest_catalog(q="roter droide", item_type="minifig",
                             user={"id": 1})
    namen = [x["item_id"] for x in d["items"]]
    assert len(namen) == 6, namen
    assert "sw900" not in namen, "der weitere Begriff darf nicht anhängen"
