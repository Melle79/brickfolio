"""Was der Katalogdienst zusichert.

Die beiden Läufe selbst sind aus der App übernommen und dort über Tage an
echten Daten gereift – ihre Tests stehen im Hauptrepo. Hier geht es um das,
was neu ist: die Schnittstelle, die die Konsole bedient, und die Trennung
der beiden Token.
"""
import os
import sys
import time

import json
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "steuern")
    monkeypatch.setenv("LESE_TOKEN", "lesen")
    import katalog
    monkeypatch.setattr(katalog, "DB_PATH", str(tmp_path / "k.db"))
    katalog.init_db()
    import dienst
    c = TestClient(dienst.app)
    c.headers["Authorization"] = "Bearer steuern"
    return c


def _zeile(item_no="cas001", merkmale="", stand=100):
    import katalog
    with katalog.db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO katalog_index (item_no, item_type, name,"
            " such, img_url, merkmale, updated_at) VALUES (?, 'minifig',"
            " 'Dragon Master', 'dragonmaster', 'u', ?, ?)",
            (item_no, merkmale, stand))


def test_ohne_token_geht_nichts(client):
    """Ein offener Katalogdienst im Heimnetz könnte fremdes Kontingent
    verbrennen – BrickLink lässt 5.000 Abrufe am Tag zu, und dasselbe
    Kontingent trägt die Preisabfragen der Instanzen."""
    c = TestClient(client.app)
    assert c.get("/api/status").status_code == 401
    assert c.post("/api/abzug/start").status_code == 401
    # Der Lebenszeichen-Endpunkt bleibt offen, sonst ließe sich von außen
    # nicht prüfen, ob der Dienst überhaupt läuft.
    assert c.get("/api/health").status_code == 200


def test_der_lesetoken_darf_nicht_steuern(client):
    """Eine Instanz soll den Abzug beziehen können, ohne ihn zu steuern."""
    c = TestClient(client.app)
    c.headers["Authorization"] = "Bearer lesen"
    assert c.get("/api/status").status_code == 401
    assert c.post("/api/abzug/start").status_code == 401
    assert c.get("/api/index?token=lesen").status_code == 200


def test_der_admintoken_darf_auch_lesen(client):
    _zeile()
    assert client.get("/api/index?token=steuern").status_code == 401, \
        "der Admin-Token gilt hier nicht – es ist ein eigener Kanal"
    assert client.get("/api/index?token=lesen").json()["gesamt"] == 1


def test_der_stand_zaehlt_frisch_statt_aus_dem_speicher(client):
    """Als Feld im Laufzustand stand `offen` nach jedem Neustart auf 0, und
    die Oberfläche meldete „alle Bilder angesehen", während in Wahrheit
    8.328 Figuren offen waren (gesehen am 22.08.2026)."""
    _zeile("cas001", merkmale="")
    _zeile("cas002", merkmale="torso red")
    z = client.get("/api/status").json()["zeilen"]
    assert z == {"gesamt": 2, "offen": 1, "beschrieben": 1}


def test_themen_dazu_und_ruhen_lassen(client):
    assert client.post("/api/themen", json={"praefix": "wtf"}).json()["ok"]
    themen = {t["praefix"]: t for t in client.get("/api/status").json()["themen"]}
    assert themen["wtf"]["aktiv"] == 1
    client.delete("/api/themen/wtf")
    themen = {t["praefix"]: t for t in client.get("/api/status").json()["themen"]}
    assert themen["wtf"]["aktiv"] == 0


def test_nur_buchstaben_als_praefix(client):
    """Das Präfix wandert in eine Adresse – „../" hätte dort nichts zu
    suchen. Zu lange Werte weist schon Pydantic ab (422), der Rest der
    Prüfung liegt im Endpunkt (400); beides ist eine Ablehnung."""
    # „x" fehlt hier bewusst: Ein einzelnes Zeichen ist gültig, seit
    # BrickLinks `s` (Classic Town) aufgetaucht ist.
    for unsinn in ("", "../etc", "viel-zu-lang", "sw 1", "a/b"):
        code = client.post("/api/themen", json={"praefix": unsinn}).status_code
        assert code >= 400, "%s wurde angenommen" % unsinn


def test_ohne_bricklink_kein_abzug(client):
    """Statt in einen 401-Regen zu laufen und ihn für Lücken zu halten."""
    r = client.post("/api/abzug/start")
    assert r.status_code == 400 and "BrickLink" in r.json()["detail"]


def test_die_seite_endet_am_letzten_zeitstempel(client):
    """`stand` ist der Zeitstempel der letzten gelieferten Zeile, nicht die
    Uhrzeit: Sonst übersähe der nächste Abruf alles, was zwischen Abfrage
    und Antwort geschrieben wurde."""
    _zeile("a001", stand=100)
    _zeile("a002", stand=200)
    d = client.get("/api/index?token=lesen&limit=1").json()
    assert d["stand"] == 100 and d["mehr"] is True
    d2 = client.get("/api/index?token=lesen&limit=1&seit=100").json()
    assert [z["item_no"] for z in d2["zeilen"]] == ["a002"]


def test_eine_leere_seite_haelt_den_stand(client):
    """Sonst fiele der Wasserstand der Instanz auf 0 zurück und sie zöge
    beim nächsten Mal den ganzen Abzug erneut."""
    d = client.get("/api/index?token=lesen&seit=500").json()
    assert d["zeilen"] == [] and d["stand"] == 500 and d["mehr"] is False


# ----------------------------------------- Was hinaus darf und was nicht

def test_nur_nummer_und_eigene_beschreibung_gehen_hinaus(client):
    """Der Kern der Sache. Name, Jahr, Kategorie und Bildadresse sind
    BrickLinks Inhalt – deren Nutzungsbedingungen untersagen die Weitergabe
    an Dritte ausdrücklich. Was hinausgeht, ist eine Kennung und ein Text,
    den unser Sehmodell über ein Foto geschrieben hat."""
    import json as j
    import katalog
    with katalog.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " img_url, category_id, jahr, farben, art, merkmale, modell,"
            " updated_at) VALUES ('cas001', 'minifig', 'Dragon Master',"
            " 'dragonmaster', 'https://img.bricklink.com/ML/cas001.jpg',"
            " '53', 1993, 'red, yellow', 'knight',"
            " 'cape yellow green dragon', 'qwen3-vl:latest', 100)")

    import veroeffentlichen
    text, anzahl = veroeffentlichen.index_bauen()
    assert anzahl == 1
    d = j.loads(text.strip())
    assert d == {"item_no": "cas001", "art": "knight", "farben": "red, yellow",
                 "merkmale": "cape yellow green dragon",
                 "modell": "qwen3-vl:latest"}
    for verboten in ("Dragon Master", "dragonmaster", "img.bricklink.com",
                     "1993", "53"):
        assert verboten not in text, "%s ist mit hinausgegangen" % verboten


def test_unbeschriebene_figuren_bleiben_draussen(client):
    """Eine Zeile, die nur aus einer Nummer besteht, hilft niemandem beim
    Suchen und bläht die Datei auf."""
    import katalog
    with katalog.db() as conn:
        for nr, merk in (("a001", ""), ("a002", "–"), ("a003", "torso red")):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such,"
                " merkmale, updated_at) VALUES (?, 'minifig', 'x', 'x', ?, 1)",
                (nr, merk))
    import veroeffentlichen
    text, anzahl = veroeffentlichen.index_bauen()
    assert anzahl == 1 and "a003" in text
    assert "a001" not in text and "a002" not in text


def test_die_datei_ist_nach_nummer_sortiert(client):
    """Damit ein Commit die geänderten Zeilen zeigt und nicht die ganze
    Datei – bei 9.741 Einträgen ist das der Unterschied zwischen einem
    lesbaren Verlauf und keinem."""
    import katalog
    with katalog.db() as conn:
        for nr in ("sw0100", "cas001", "njo0050"):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such,"
                " merkmale, updated_at) VALUES (?, 'minifig', 'x', 'x',"
                " 'torso red', 1)", (nr,))
    import veroeffentlichen
    text, _ = veroeffentlichen.index_bauen()
    nummern = [__import__("json").loads(z)["item_no"]
               for z in text.strip().split("\n")]
    assert nummern == sorted(nummern)


def test_ohne_github_kein_veroeffentlichen(client, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    r = client.post("/api/veroeffentlichen")
    assert r.status_code == 400 and "GITHUB" in r.json()["detail"]


def test_die_vorschau_zeigt_was_hinausginge(client):
    """Vor dem ersten Mal will man sehen, was da wirklich veröffentlicht
    wird. Ein Blick auf drei Zeilen beantwortet das besser als jede
    Zusicherung."""
    import katalog
    with katalog.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " merkmale, updated_at) VALUES ('cas001', 'minifig', 'Geheim',"
            " 'geheim', 'torso red', 1)")
    d = client.get("/api/veroeffentlichen/vorschau").json()
    assert d["zeilen"] == 1
    assert d["felder"] == ["item_no", "art", "farben", "merkmale", "modell"]
    assert "Geheim" not in " ".join(d["probe"])


# ------------------------------------------------------- Einstellungen

def test_geheimnisse_kommen_nie_zurueck(client):
    """Angezeigt wird nur, ob und wie lang etwas hinterlegt ist. Das
    schützt nicht gegen Zugriff auf die NAS, aber gegen alles davor – und
    gegen ein versehentliches Bildschirmfoto."""
    client.post("/api/einstellungen",
                json={"werte": {"BL_TOKEN": "streng-geheim-123",
                                "GITHUB_REPO": "Melle79/brickfolio"}})
    d = client.get("/api/einstellungen").json()
    felder = {f["name"]: f for f in d["felder"]}
    assert felder["BL_TOKEN"]["wert"] == ""
    assert felder["BL_TOKEN"]["gesetzt"] == "gesetzt (17 Zeichen)"
    # Nicht-Geheimes darf man sehen – sonst könnte man einen Tippfehler im
    # Repo-Namen nie finden.
    assert felder["GITHUB_REPO"]["wert"] == "Melle79/brickfolio"
    assert "streng-geheim" not in client.get("/api/einstellungen").text


def test_ein_leeres_feld_laesst_den_wert_stehen(client):
    """Sonst löschte jedes Speichern die neun Felder, die man gerade nicht
    angefasst hat."""
    client.post("/api/einstellungen", json={"werte": {"BL_TOKEN": "abc"}})
    client.post("/api/einstellungen", json={"werte": {"BL_TOKEN": "",
                                                      "GITHUB_BRANCH": "main"}})
    import katalog
    assert katalog.konfig("BL_TOKEN") == "abc"
    assert katalog.konfig("GITHUB_BRANCH") == "main"


def test_die_konsole_hat_vorrang_vor_der_umgebung(client, monkeypatch):
    """Wer in der Konsole etwas einträgt, will damit arbeiten – auch wenn
    in der Umgebung noch der alte Wert steht."""
    monkeypatch.setenv("GITHUB_BRANCH", "aus-der-umgebung")
    import katalog
    katalog.konfig_vergessen()
    assert katalog.konfig("GITHUB_BRANCH") == "aus-der-umgebung"
    client.post("/api/einstellungen",
                json={"werte": {"GITHUB_BRANCH": "aus-der-konsole"}})
    assert katalog.konfig("GITHUB_BRANCH") == "aus-der-konsole"
    felder = {f["name"]: f for f in
              client.get("/api/einstellungen").json()["felder"]}
    assert felder["GITHUB_BRANCH"]["quelle"] == "Konsole"


def test_der_gemerkte_wert_wird_beim_schreiben_verworfen(client, monkeypatch):
    """Ohne das arbeitete der laufende Prozess mit dem alten Wert weiter,
    und man sucht den Fehler an der falschen Stelle."""
    import katalog
    client.post("/api/einstellungen", json={"werte": {"OLLAMA_URL": "http://a"}})
    assert katalog.konfig("OLLAMA_URL") == "http://a"
    client.post("/api/einstellungen", json={"werte": {"OLLAMA_URL": "http://b"}})
    assert katalog.konfig("OLLAMA_URL") == "http://b"


def test_unbekannte_felder_werden_abgewiesen(client):
    r = client.post("/api/einstellungen",
                    json={"werte": {"PATH": "/etc/boese"}})
    assert r.status_code == 400


# --------------------------------------------- Was die Themenliste anzeigt

def test_die_themenliste_zeigt_den_bestand_nicht_den_letzten_lauf(client):
    """Am 24.08.2026 stand bei jedem der achtzehn Themen „0 Figuren
    gefunden", obwohl 9.741 im Index lagen. `gefunden` zählt nur den
    **letzten** Lauf – und der findet nach dem ersten Durchgang nichts
    Neues mehr."""
    import katalog
    with katalog.db() as conn:
        # `cas` steht schon in der Standardliste – nur den Zähler setzen.
        conn.execute("UPDATE katalog_lauf SET gefunden = 0 "
                     "WHERE praefix = 'cas'")
        for i in (1, 2, 3):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such,"
                " merkmale, updated_at) VALUES (?, 'minifig', 'x', 'x',"
                " 'torso red', 1)", ("cas%03d" % i,))
        # Ein Thema, dessen Präfix ein Anfang eines anderen ist: `cas` darf
        # `castle001` nicht mitzählen, sonst stimmt keine Zahl mehr.
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " merkmale, updated_at) VALUES ('castle001', 'minifig', 'x',"
            " 'x', 'torso red', 1)")

    themen = {t["praefix"]: t for t in client.get("/api/status").json()["themen"]}
    assert themen["cas"]["im_index"] == 3, themen["cas"]


def test_die_gemessene_ziffernbreite_bleibt_stehen(client, monkeypatch):
    """Sie jedes Mal neu zu ermitteln kostet bis zu zehn Abrufe je Thema –
    bei achtzehn Themen 180 für eine Antwort, die sich nie ändert."""
    import katalog
    import laeufe
    with katalog.db() as conn:
        conn.execute("INSERT INTO katalog_lauf (praefix) VALUES ('zz')")

    gemessen = []
    monkeypatch.setattr(laeufe, "_katalog_breite",
                        lambda p: (gemessen.append(p), 3)[1])
    monkeypatch.setattr(laeufe, "bricklink_item",
                        lambda t, n: (_ for _ in ()).throw(
                            __import__("requests").HTTPError("404")))
    monkeypatch.setattr(laeufe, "KATALOG_TAKT", 0)
    monkeypatch.setattr(laeufe, "KATALOG_LUECKE", 2)

    laeufe._katalog_anbau("zz")
    assert gemessen == ["zz"]
    with katalog.db() as conn:
        assert conn.execute("SELECT breite FROM katalog_lauf WHERE "
                            "praefix='zz'").fetchone()["breite"] == 3

    laeufe._katalog_anbau("zz")
    assert gemessen == ["zz"], "die Breite wurde ein zweites Mal gemessen"


def test_bricklink_namen_werden_entschluesselt(client, monkeypatch):
    """BrickLink liefert sie HTML-kodiert: „Tina, Orange Torso &#40;4143766&#41;".
    Ungefiltert stünde das so in der Suche und in jeder Anzeige."""
    import katalog

    class Fake:
        status_code = 200

        def json(self):
            return {"meta": {"code": 200},
                    "data": {"name": "Tina &#40;4143766&#41;"}}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(katalog.requests, "get", lambda *a, **k: Fake())
    monkeypatch.setattr(katalog, "bl_auth", lambda: None)
    d = katalog.bricklink_item("minifig", "cre001")
    assert d["name"] == "Tina (4143766)"


def test_ziffern_im_praefix_sind_erlaubt(client):
    """BrickLink führt `4j` für die Reihe „4 Juniors" – `4j011` ist
    Cannonball Jimmy. „Nur Buchstaben" wies das Thema ab, obwohl es die
    Figuren gibt (gesehen am 24.08.2026)."""
    r = client.post("/api/themen", json={"praefix": "4j"})
    assert r.status_code == 200 and r.json()["praefix"] == "4j"


def test_ein_einzelnes_zeichen_ist_gueltig(client):
    """BrickLink führt `s` für Classic Town – `s001` ist eine Feuerwehrfigur.
    „Mindestens zwei Zeichen" wies das Thema ab, obwohl es 19.158 Figuren im
    Katalog gibt und ein Teil davon genau dort hängt."""
    r = client.post("/api/themen", json={"praefix": "s"})
    assert r.status_code == 200 and r.json()["praefix"] == "s"


def test_varianten_werden_mitgenommen(client, monkeypatch):
    """Die offizielle Dokumentation nennt das Format
    `{Series}{Sequential}{Variant}` mit Beispiel `sw0073a` – und das ist
    tatsächlich eine andere Figur als `sw0073` („Dark Bluish Gray Body"
    statt „Light and Dark Gray"). Ohne die Variantenschleife fehlt jede
    davon."""
    import katalog
    import laeufe

    katalog_daten = {
        "zz001": "Grundfigur",
        "zz001a": "Variante A",
        "zz001b": "Variante B",
        # kein `c` – dort muss die Schleife abbrechen
    }
    gefragt = []

    def fake(item_type, item_no):
        gefragt.append(item_no)
        if item_no not in katalog_daten:
            import requests
            resp = requests.Response()
            resp.status_code = 404
            raise requests.HTTPError("404", response=resp)
        return {"name": katalog_daten[item_no], "category_id": 1,
                "year_released": 2000}

    monkeypatch.setattr(laeufe, "bricklink_item", fake)
    monkeypatch.setattr(laeufe, "_katalog_breite", lambda p: 3)
    monkeypatch.setattr(laeufe, "KATALOG_TAKT", 0)
    monkeypatch.setattr(laeufe, "KATALOG_LUECKE", 2)
    with katalog.db() as conn:
        conn.execute("INSERT INTO katalog_lauf (praefix, breite) "
                     "VALUES ('zz', 3)")

    laeufe._katalog_anbau("zz")

    with katalog.db() as conn:
        drin = sorted(r["item_no"] for r in
                      conn.execute("SELECT item_no FROM katalog_index"))
    assert drin == ["zz001", "zz001a", "zz001b"]
    # Nach dem fehlenden `c` darf sie nicht weitersuchen.
    assert "zz001d" not in gefragt


# --------------------------------- Bindewörter am Ende der Wortgrenze

def test_ein_bindewort_bleibt_nicht_am_ende_stehen():
    """„holding orange tool pouch with" sind genau vier Wörter, „a small
    black dot on the" genau zwölf. Die Grenze schnitt richtig ab und ließ
    das Bindewort stehen – 352 von 19.201 Beschreibungen sahen dadurch
    kaputt aus (26.08.2026)."""
    from bild import _bild_wort
    assert _bild_wort("orange tool pouch with", 4) == "orange tool pouch"
    assert _bild_wort("smiling face with black eyes and a small black dot "
                      "on the wall", 12) == \
        "smiling face with black eyes and a small black dot"


def test_die_grenze_selbst_bleibt():
    """Ein ganzer Satz im Suchtext trifft irgendwann alles."""
    from bild import _bild_wort
    assert _bild_wort("red blue green yellow black white", 3) == \
        "red blue green"


def test_ein_bindewort_in_der_mitte_bleibt_stehen():
    """Nur am Ende trägt es nichts – „face with black eyes" braucht es."""
    from bild import _bild_wort
    assert _bild_wort("face with black eyes", 12) == "face with black eyes"


def test_acht_teile_passen_hinein():
    """Kopf, Haar, Helm, Torso, Arme, Beine sind schon sechs – ein Umhang
    verdrängte bei der alten Grenze etwas. 4.623 Figuren saßen genau
    darauf, und die Verteilung endete dort hart."""
    from bild import _BILD_SCHEMA
    assert _BILD_SCHEMA["properties"]["parts"]["maxItems"] == 8


# --------------------------------- Die Wahl des Sehmodells

def test_die_vorgabe_ist_das_gemessene_modell():
    """Die Vorgabe stand auf dem Schlusslicht der eigenen Messung.

    `minicpm-v:latest` stammte aus der Zeit, als es das einzige Sehmodell
    auf dem Mac mini war. Am 21.08.2026 wurde gemessen: `qwen3-vl` erkannte
    R-3PO, den AT-AT-Fahrer und Darth Vader richtig, `minicpm-v` verfehlte
    die Art in zwei von drei Proben. Die Messung stand im Changelog, die
    Vorgabe blieb trotzdem stehen – wer frisch aufsetzt und
    `OLLAMA_BILD_MODEL` nicht kennt, bekam das schwächste Modell.

    Der Test hängt an einer Konstante, und das ist hier Absicht: Die
    Konstante **ist** die Entscheidung, und `konfig()` fällt bei jeder
    frischen Aufsetzung still auf sie zurück.
    """
    import bild
    assert bild.OLLAMA_BILD_STD == "qwen3-vl:latest"


def test_ohne_einstellung_greift_die_vorgabe(monkeypatch):
    """Die Vorgabe ist kein totes Stück Text – sie ist der Normalfall.

    Sie greift überall dort, wo `OLLAMA_BILD_MODEL` nicht gesetzt ist, also
    bei jeder frischen Aufsetzung.
    """
    import bild
    import katalog
    monkeypatch.setattr(katalog, "konfig", lambda name: "")
    assert bild.ollama_bild_modell() == "qwen3-vl:latest"


def test_der_vergleich_fragt_wirklich_das_genannte_modell(monkeypatch):
    """Ein ignorierter Modellparameter wäre der schlimmste Fehler hier.

    Der Modellvergleich schickt dieselben Figuren an mehrere Modelle. Käme
    der Name nicht bis in die Anfrage durch, verglichen sich zwei Läufe
    desselben Modells miteinander – und das Ergebnis sähe völlig plausibel
    aus: zwei Spalten, leicht unterschiedliche Zeiten, ähnliche Antworten.
    Genau daraus würde dann eine Modellentscheidung abgeleitet.
    """
    import bild
    gesehen = {}

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": '{"kind": "droid", "parts": []}'}}

    def fake_post(url, **kw):
        gesehen["modell"] = kw["json"]["model"]
        return Fake()

    monkeypatch.setattr(bild, "ollama_url", lambda: "http://127.0.0.1:11434")
    monkeypatch.setattr(bild.requests, "post", fake_post)

    bild.bild_merkmale(b"nicht-leer", modell="gemma3:12b")
    assert gesehen["modell"] == "gemma3:12b"

    # Ohne Angabe bleibt es bei der Einstellung – der Lauf selbst darf sich
    # durch den Parameter nicht ändern.
    monkeypatch.setattr(bild, "ollama_bild_modell", lambda: "eingestellt:1")
    bild.bild_merkmale(b"nicht-leer")
    assert gesehen["modell"] == "eingestellt:1"


# --------------------------------- Das Vergleichswerkzeug

def _vergleich_laden():
    """`tools/bildmodelle-vergleich.py` hat einen Bindestrich im Namen und
    ist damit nicht importierbar – über den Pfad geht es trotzdem."""
    import importlib.util
    pfad = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools", "bildmodelle-vergleich.py")
    spec = importlib.util.spec_from_file_location("bildvergleich", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_jedes_bild_wird_nur_einmal_geholt(monkeypatch):
    """Sonst misst der Vergleich BrickLinks CDN mit.

    Die Bilder liegen bei BrickLink, nicht im Haus. Würde je Modell neu
    geholt, steckte in jeder Zeitmessung eine Netzlaufzeit, die mit dem
    Modell nichts zu tun hat – und bei drei Modellen über 30 Figuren wären
    es 90 Abrufe statt 30 an einem fremden Server.

    Der Test hält die Reihenfolge fest, aus der das folgt: erst alle Bilder
    holen, dann Modell außen, Figur innen.
    """
    mod = _vergleich_laden()
    geholt = []

    monkeypatch.setattr(mod.bildmodul, "bild_holen",
                        lambda url, hosts=None: geholt.append(url) or b"roh")
    monkeypatch.setattr(mod.bildmodul, "bild_vorbereiten",
                        lambda roh, kante=512: b"bild-" + roh)
    monkeypatch.setattr(mod.bildmodul, "ollama_enabled", lambda: True)
    monkeypatch.setattr(mod.bildmodul, "bild_merkmale",
                        lambda bild, modell="": {"art": "droid", "farben": [],
                                                 "merkmale": "torso red",
                                                 "fehler": ""})
    monkeypatch.setattr(sys, "argv",
                        ["x", "--modelle", "a:1,b:2,c:3",
                         "--figuren", "cas001,sw0326", "--url",
                         "http://127.0.0.1:11434", "--db", "/gibt-es-nicht"])
    mod.main()

    assert len(geholt) == 2, "je Figur ein Abruf, nicht je Figur und Modell"
    assert sorted(geholt) == sorted(set(geholt))


def test_die_erste_figur_faellt_aus_dem_median(monkeypatch):
    """Die erste Figur trägt die Ladezeit des Modells.

    Ollama lädt das Modell beim ersten Aufruf – `minicpm-v` brauchte dafür
    3,8 s gegenüber 2,8 s für die eigentliche Analyse. Zählte dieser Wert
    mit, sähe bei kleinen Stichproben jedes Modell langsam aus, und zwar
    genau um seine Dateigröße.
    """
    mod = _vergleich_laden()
    monkeypatch.setattr(mod.bildmodul, "bild_merkmale",
                        lambda bild, modell="": {"art": "", "farben": [],
                                                 "merkmale": "", "fehler": ""})
    gemessen = mod.messen(["a:1"], ["f1", "f2"], {"f1": b"x", "f2": b"y"})
    assert gemessen["a:1"]["f1"]["erste"] is True
    assert gemessen["a:1"]["f2"]["erste"] is False

    # Fehlt zur ersten Figur das Bild (BrickLink liefert nicht zu jeder
    # eines), rutscht die Ladezeit in die zweite – markiert werden muss
    # deshalb die erste **gemessene**, nicht die erste der Liste.
    gemessen = mod.messen(["a:1"], ["ohne", "f2"], {"f2": b"y"})
    assert "ohne" not in gemessen["a:1"]
    assert gemessen["a:1"]["f2"]["erste"] is True


def test_ein_nicht_befragbares_modell_haelt_den_vergleich_nicht_auf(
        monkeypatch):
    """Ein Tippfehler im Modellnamen kostete sonst eine Stunde.

    `qwen2.5:14b` gegen `qwen2.5-14b`: Die Verbindung steht, nur das Modell
    gibt es nicht – der Fehler sieht aus wie ein kaputter Dienst und ist der
    Grund, warum die Verwaltung die Modelle überhaupt zur Auswahl anbietet.

    Im Vergleich wiegt er schwerer als in der App: Jeder Fehlversuch läuft
    in die Zeitgrenze von 120 s, und bei 30 Figuren wäre das eine Stunde für
    eine am Ende leere Spalte.

    **Die unbrauchbare Antwort zählt dabei nicht mit.** Ein Modell, das
    antwortet und dabei entgleist, ist ein Ergebnis des Vergleichs – wer es
    hier abbräche, verlöre genau die Beobachtung, für die er misst.
    """
    mod = _vergleich_laden()
    gefragt = []

    def fake_merkmale(bild, modell=""):
        gefragt.append(modell)
        if modell == "gibtsnicht:1":
            return {"art": "", "farben": [], "merkmale": "",
                    "fehler": "ConnectionError: model not found"}
        return {"art": "droid", "farben": [], "merkmale": "torso red",
                "unbrauchbar": True, "fehler": "JSONDecodeError: x"}

    monkeypatch.setattr(mod.bildmodul, "bild_merkmale", fake_merkmale)
    figuren = ["f%d" % i for i in range(10)]
    bilder = {f: b"x" for f in figuren}

    mod.messen(["gibtsnicht:1", "entgleist:1"], figuren, bilder)

    assert gefragt.count("gibtsnicht:1") == mod.AUFGEBEN_NACH, \
        "nach drei Ausfällen in Folge ist Schluss"
    assert gefragt.count("entgleist:1") == 10, \
        "unbrauchbare Antworten sind ein Ergebnis, kein Abbruchgrund"
# ------------------------------------- Fehlende Grundteile nachfragen

def test_ergaenzen_fragt_nur_nach_dem_was_fehlt(monkeypatch):
    """Beim Triceratops-Kostüm beschrieb das Modell den Kopf und war
    fertig – Torso, Arme und Beine fehlten. Ein voller zweiter Lauf ist
    gemessen schädlich (15 % besser, 25 % schlechter), eine Nachfrage nur
    nach dem Fehlenden kann nichts verlieren (26.08.2026)."""
    import bild
    gefragt = {}

    class Antwort:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": json.dumps({"parts": [
                {"part": "torso", "color": "light green", "print": "white lines"},
                {"part": "arms", "color": "light green", "print": "brown spots"},
                {"part": "arms", "color": "light green", "print": "brown spots"},
                {"part": "head", "color": "olive", "print": "horns"}]})}}

    def gefaelscht(url, json=None, **k):
        gefragt["frage"] = json["messages"][0]["content"]
        return Antwort()

    monkeypatch.setattr(bild, "ollama_enabled", lambda: True)
    monkeypatch.setattr(bild, "ollama_url", lambda: "http://x")
    monkeypatch.setattr(bild, "ollama_bild_modell", lambda: "m")
    monkeypatch.setattr(bild.requests, "post", gefaelscht)

    aus = bild.merkmale_ergaenzen(b"bild", "head olive green triceratops head")
    # Nur die fehlenden drei stehen in der Frage, `head` nicht.
    assert "torso, arms, legs" in gefragt["frage"]
    # `head` war schon da und wird nicht angehängt; die Arme nur einmal.
    assert aus == ("torso light green white lines; "
                   "arms light green brown spots")


def test_ergaenzen_haelt_still_wenn_nichts_fehlt(monkeypatch):
    """Sonst liefe für jede vollständige Figur ein zweiter Modellaufruf."""
    import bild
    monkeypatch.setattr(bild, "ollama_enabled", lambda: True)
    monkeypatch.setattr(bild.requests, "post",
                        lambda *a, **k: pytest.fail("nicht fragen"))
    assert bild.merkmale_ergaenzen(
        b"x", "head yellow; torso red; arms yellow; legs blue") == ""
