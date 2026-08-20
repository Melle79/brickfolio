"""„Ritter" fand nichts, obwohl die Figuren im Regal lagen.

Die Oberfläche ist deutsch, die Sammlungsnamen kommen von BrickLink und sind
**englisch**. Die Sammlungssuche ist ein reines `LIKE '%…%'` auf Name und
Nummer – wer „Ritter" eintippte, bekam eine leere Liste, obwohl die Figur als
„Castle Knight" in der eigenen Datenbank steht. Das war kein Randfall, sondern
die naheliegendste Suche eines deutschen Nutzers.

Seit 2.28.0 fragt die App in genau diesem Fall eine **optionale** lokale KI
nach englischen Begriffen und sucht damit erneut. Entscheidend und hier
geprüft: Das Modell liefert nur **Suchbegriffe**, niemals Ergebnisse – jede
Zeile kommt weiter aus der eigenen Datenbank. Ohne eingerichtete KI und bei
jedem Fehlschlag verhält sich die Suche exakt wie vorher.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "ki.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('sven', 'x', 1, 1, ?)",
                     (now,))
        # Genau der Fall aus dem Vorfall: englischer Name, deutsche Suche.
        for item_id, name in (("cas315", "Castle Knight with Sword"),
                              ("pi123", "Pirate Captain"),
                              ("sw0815", "Luke Skywalker"),
                              # Schreibweise mit Bindestrich – getippt wird
                              # „c3 po", und genau daran scheiterte es.
                              ("sw0653", "C-3PO - Red Arm"),
                              ("sw0010", "C-3PO"),
                              ("njo123", "Ninja - Blue")):
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity,"
                " condition, added_at, added_by) "
                "VALUES (?, 'minifig', ?, 1, 'used', ?, 1)",
                (item_id, name, now))
    integrations._begriff_cache.clear()
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def _ollama(monkeypatch, antwort, mitzaehler=None):
    """Ollama vortäuschen. `antwort` ist die Begriffsliste des Modells."""
    import json as json_mod

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content":
                                json_mod.dumps({"begriffe": antwort})}}

    def fake_post(url, **kw):
        if mitzaehler is not None:
            mitzaehler.append(url)
        return Fake()

    monkeypatch.setattr(integrations.requests, "post", fake_post)


def _einrichten(client):
    r = client.post("/api/settings/ollama",
                    json={"url": "http://127.0.0.1:11434", "model": "test"})
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is True


# --------------------------------------------------------------- der Vorfall

def test_deutscher_begriff_findet_die_englisch_benannte_figur(client,
                                                              monkeypatch):
    """Der eigentliche Vorfall: „Ritter" muss den „Castle Knight" finden."""
    # Vorher: die normale Suche findet nichts. Genau das war das Problem.
    leer = client.get("/api/collection?q=Ritter").json()
    assert leer["items"] == []

    _einrichten(client)
    _ollama(monkeypatch, ["Knight", "Medieval Figure"])

    r = client.get("/api/collection/suggest?q=Ritter")
    assert r.status_code == 200, r.text
    daten = r.json()
    namen = [i["name"] for i in daten["items"]]
    assert "Castle Knight with Sword" in namen
    # Nur Begriffe melden, die auch getroffen haben – „Medieval Figure"
    # findet nichts und hat im Hinweis nichts zu suchen.
    assert daten["begriffe"] == ["Knight"]


# ------------------------------------------------- Schreibweise der Eigennamen

def test_c3po_ohne_bindestriche_findet_die_figur(client, monkeypatch):
    """„c3 po" gegen „C-3PO" – der Fall, an dem die erste Fassung scheiterte.

    BrickLink schreibt die bekanntesten Figuren mit Bindestrich (`C-3PO`,
    `R2-D2`), getippt wird ohne. Ein LIKE auf die rohe Zeichenkette fand
    deshalb ausgerechnet dort nichts. Der Vergleich lässt jetzt Satzzeichen
    weg.
    """
    _einrichten(client)
    _ollama(monkeypatch, ["C-3PO"])

    namen = [i["name"] for i in
             client.get("/api/collection/suggest?q=c3 po").json()["items"]]
    assert "C-3PO" in namen and "C-3PO - Red Arm" in namen


def test_eigenschaft_grenzt_ein_statt_alles_zu_zeigen(client, monkeypatch):
    """„roter c3 po" soll den roten liefern, nicht jeden C-3PO.

    Das Modell gibt dafür erst den reinen Namen und dann die Variante aus.
    Der zweite Begriff muss genauer treffen als der erste.
    """
    _einrichten(client)
    # Genau das liefert qwen2.5:14b hier, in dieser Reihenfolge – gemessen
    # in zehn von zehn Laeufen.
    _ollama(monkeypatch, ["C-3PO", "C-3PO (red)"])

    daten = client.get("/api/collection/suggest?q=roter c3 po").json()
    namen = [i["name"] for i in daten["items"]]
    # Der rote steht oben, obwohl das Modell den breiten Begriff zuerst nennt.
    # In Modellreihenfolge haette „C-3PO" alle drei eingesammelt und die
    # Farbvariante waere ohne neuen Treffer geblieben.
    assert namen[0] == "C-3PO - Red Arm", namen
    assert "C-3PO" in namen, "die uebrigen sollen als Rueckfall dabeibleiben"
    assert daten["begriffe"][0] == "C-3PO (red)"


def test_wortdreher_findet_den_artikel(client, monkeypatch):
    """Das Modell sagt „Blue-Ninja", der Artikel heißt „Ninja - Blue"."""
    _einrichten(client)
    _ollama(monkeypatch, ["Blue-Ninja"])

    namen = [i["name"] for i in
             client.get("/api/collection/suggest?q=blauer Ninja").json()["items"]]
    assert namen == ["Ninja - Blue"]


def test_mehrwortbegriffe_brauchen_alle_woerter(client, monkeypatch):
    """Sonst zöge „Knight Hunter" jeden Ritter herein.

    Der Begriff existiert in der Sammlung nicht – er darf nichts liefern,
    obwohl „Knight" allein sehr wohl etwas fände.
    """
    _einrichten(client)
    _ollama(monkeypatch, ["Knight Hunter"])

    daten = client.get("/api/collection/suggest?q=Ritter").json()
    assert daten["items"] == []
    assert daten["begriffe"] == []


# ------------------------------------------------------------------ optional

def test_ohne_eingerichtete_ki_passiert_nichts(client, monkeypatch):
    """Nicht jeder hat eine lokale KI – ohne Adresse bleibt alles beim Alten."""
    gerufen: list = []
    _ollama(monkeypatch, ["Knight"], mitzaehler=gerufen)

    daten = client.get("/api/collection/suggest?q=Ritter").json()
    assert daten == {"begriffe": [], "items": []}
    assert gerufen == [], "ohne Adresse darf nichts nach außen gehen"
    assert client.get("/api/config").json()["ki_suche"] is False


def test_stummer_dienst_laesst_die_suche_unberuehrt(client, monkeypatch):
    """Ollama aus, Netz weg, falscher Port: Die Suche darf nicht scheitern."""
    _einrichten(client)

    def kaputt(url, **kw):
        raise OSError("Verbindung abgelehnt")

    monkeypatch.setattr(integrations.requests, "post", kaputt)

    r = client.get("/api/collection/suggest?q=Ritter")
    assert r.status_code == 200
    assert r.json() == {"begriffe": [], "items": []}
    # Und die gewöhnliche Suche läuft weiter.
    assert client.get("/api/collection?q=Pirate").json()["items"]


# ----------------------------------------------------- Modell erfindet nichts

def test_das_modell_kann_keine_figur_erfinden(client, monkeypatch):
    """Der Grund, warum ein kleines lokales Modell hier genügt.

    Selbst wenn es Unsinn zurückgibt, entsteht daraus kein Eintrag: Gesucht
    wird ausschließlich in der eigenen Datenbank.
    """
    _einrichten(client)
    _ollama(monkeypatch, ["Millennium Falcon", "Batmobile", "Hogwarts"])

    daten = client.get("/api/collection/suggest?q=Quatsch").json()
    assert daten["items"] == []
    assert daten["begriffe"] == []


def test_treffer_stammen_immer_aus_der_eigenen_sammlung(client, monkeypatch):
    """Jede gelieferte Zeile muss es in der Datenbank wirklich geben."""
    _einrichten(client)
    _ollama(monkeypatch, ["Pirate", "Knight"])

    daten = client.get("/api/collection/suggest?q=Seeraeuber").json()
    with core.db() as conn:
        echte = {r["id"] for r in conn.execute("SELECT id FROM collection")}
    assert daten["items"], "es sollte etwas gefunden werden"
    for eintrag in daten["items"]:
        assert eintrag["id"] in echte


def test_jede_zeile_nur_einmal(client, monkeypatch):
    """Zwei Begriffe, dieselbe Figur – sie darf nicht doppelt erscheinen."""
    _einrichten(client)
    _ollama(monkeypatch, ["Knight", "Castle"])

    items = client.get("/api/collection/suggest?q=Ritter").json()["items"]
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------- Sparsamkeit

def test_gleiche_frage_fragt_das_modell_nur_einmal(client, monkeypatch):
    """Die Suche feuert beim Tippen alle 300 ms.

    Ohne Zwischenspeicher liefe je Tastendruck ein Modellaufruf – bei einem
    lokalen Modell sind das jedes Mal ein bis zwei Sekunden Rechenzeit.
    """
    _einrichten(client)
    gerufen: list = []
    _ollama(monkeypatch, ["Knight"], mitzaehler=gerufen)

    for _ in range(4):
        client.get("/api/collection/suggest?q=Ritter")
    assert len(gerufen) == 1, f"{len(gerufen)} Aufrufe statt einem"


def test_ein_aussetzer_vergiftet_den_begriff_nicht(client, monkeypatch):
    """„roter c3 po" fand dauerhaft nichts, „c3 po" daneben tadellos.

    Die erste Fassung merkte sich auch die **leere** Antwort für immer. Lief
    ein einziger Aufruf in den Zeitablauf – etwa weil Ollama das Modell erst
    laden musste –, blieb genau dieser Suchbegriff bis zum Neustart tot. Ein
    Treffer darf bleiben, ein Fehlschlag nicht.
    """
    _einrichten(client)

    def kaputt(url, **kw):
        raise OSError("Zeitablauf beim Laden des Modells")

    monkeypatch.setattr(integrations.requests, "post", kaputt)
    assert client.get("/api/collection/suggest?q=Ritter").json()["items"] == []

    # Der Dienst ist wieder da – und die Uhr ein wenig weiter. Die echte
    # Zeit vorher festhalten: `integrations.time` *ist* das globale Modul,
    # ein `time.time()` in der Ersatzfunktion riefe sich selbst auf.
    _ollama(monkeypatch, ["Knight"])
    spaeter = time.time() + integrations._MISSERFOLG_GILT + 1
    monkeypatch.setattr(integrations.time, "time", lambda: spaeter)

    namen = [i["name"] for i in
             client.get("/api/collection/suggest?q=Ritter").json()["items"]]
    assert "Castle Knight with Sword" in namen, "der Aussetzer wirkt noch nach"


def test_treffer_bleiben_dauerhaft_gemerkt(client, monkeypatch):
    """Nur der Fehlschlag verfällt – ein Treffer soll nicht neu erfragt werden."""
    _einrichten(client)
    gerufen: list = []
    _ollama(monkeypatch, ["Knight"], mitzaehler=gerufen)
    client.get("/api/collection/suggest?q=Ritter")

    morgen = time.time() + 24 * 3600
    monkeypatch.setattr(integrations.time, "time", lambda: morgen)
    client.get("/api/collection/suggest?q=Ritter")
    assert len(gerufen) == 1


def test_modell_bleibt_geladen(client, monkeypatch):
    """Ohne `keep_alive` entlädt Ollama nach fünf Minuten Ruhe.

    Die Ladezeit zahlt dann ausgerechnet der, der nach einer Pause sucht –
    gemessen 1,4 s im Normalfall, aber 48,9 s bei Speicherdruck.
    """
    _einrichten(client)
    gesendet: list = []

    class Fake:
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": '{"begriffe": ["Knight"]}'}}

    def fake_post(url, **kw):
        gesendet.append(kw.get("json", {}))
        return Fake()

    monkeypatch.setattr(integrations.requests, "post", fake_post)
    client.get("/api/collection/suggest?q=Ritter")
    assert gesendet and gesendet[0].get("keep_alive"), "keep_alive fehlt"


def test_adresswechsel_leert_den_zwischenspeicher(client, monkeypatch):
    """Sonst bliebe nach dem Umstellen unerklärlich die alte Antwort stehen."""
    _einrichten(client)
    gerufen: list = []
    _ollama(monkeypatch, ["Knight"], mitzaehler=gerufen)
    client.get("/api/collection/suggest?q=Ritter")

    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11500", "model": "test"})
    client.get("/api/collection/suggest?q=Ritter")
    assert len(gerufen) == 2


# ------------------------------------------------------------- Einstellungen

def test_adresse_muss_ein_schema_haben(client):
    """„192.168.0.220:11434" ohne http:// ergibt sonst stille Fehlschläge."""
    r = client.post("/api/settings/ollama",
                    json={"url": "192.168.0.220:11434", "model": ""})
    assert r.status_code == 400


def test_leere_adresse_schaltet_wieder_ab(client):
    _einrichten(client)
    r = client.post("/api/settings/ollama", json={"url": "", "model": ""})
    assert r.json()["enabled"] is False
    assert client.get("/api/config").json()["ki_suche"] is False


def test_adresse_wird_im_klartext_zurueckgegeben(client):
    """Anders als API-Schlüssel: Eine Adresse muss man beim Einrichten sehen."""
    _einrichten(client)
    daten = client.get("/api/settings/ollama").json()
    assert daten["url"] == "http://127.0.0.1:11434"
    assert daten["default_model"] == integrations.OLLAMA_STD_MODELL


def test_adresse_steht_nicht_in_fehlerberichten(client):
    """Fehlerberichte können als öffentliches Issue enden.

    Die Adresse verrät den Aufbau des Heimnetzes und kann Zugangsdaten
    enthalten – sie gehört wie die API-Schlüssel herausgefiltert.
    """
    core.set_setting("ollama_url", "http://geheim.fritz.box:11434")
    sauber = main.scrub("Fehler bei http://geheim.fritz.box:11434 beim Abruf",
                        limit=2000)
    assert "geheim.fritz.box" not in sauber
