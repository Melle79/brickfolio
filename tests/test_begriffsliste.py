"""Die Suche lernt – und man kann ihr etwas beibringen.

Bis 2.31.0 lag die Zuordnung „deutscher Begriff → englische Katalogbegriffe"
nur im Arbeitsspeicher. Nach jedem Neustart war sie weg, **nur das Modell**
schrieb hinein, und ansehen konnte man sie gar nicht. Wer „roter c3po"
tippte, bekam für immer C-3PO-Varianten – obwohl die gesuchte Figur „R-3PO
Protocol Droid" heißt.

Die Liste hängt bewusst an der App, nicht am Modell: Ein Wechsel des Modells
nimmt den Wissensstand mit. Ein nachtrainiertes Modell täte das nicht, und
genau das war Svens Bedingung.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "bl.db"))
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


def _ollama(monkeypatch, antwort, mitzaehler=None):
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


def _ki_an(client):
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": "test"})


# --------------------------------------------------------------- der Vorfall

def test_eine_eigene_zeile_schlaegt_das_modell(client, monkeypatch):
    """Genau Svens Fall: „roter c3po" soll R-3PO finden, nicht C-3PO."""
    _ki_an(client)
    _ollama(monkeypatch, ["C-3PO", "C-3PO (Red)"])
    assert integrations.suchbegriffe("roter c3po") == ["C-3PO", "C-3PO (Red)"]

    r = client.post("/api/settings/begriffe",
                    json={"begriff": "roter c3po", "begriffe": "R-3PO"})
    assert r.status_code == 200, r.text
    assert integrations.suchbegriffe("roter c3po") == ["R-3PO"]


def test_das_modell_ueberschreibt_eine_eigene_zeile_nicht(client, monkeypatch):
    """Sonst wäre das Gelernte beim nächsten Suchlauf wieder weg."""
    _ki_an(client)
    client.post("/api/settings/begriffe",
                json={"begriff": "ritter", "begriffe": "Knight"})
    integrations.begriffe_merken("ritter", ["Minifigure", "Hero"], "ki")
    assert integrations.begriffe_gelernt("ritter")[0] == ["Knight"]


def test_von_hand_gilt_auch_ohne_ki(client):
    """Das Gelernte darf nicht an einem Dienst hängen, der damit nichts zu
    tun hat – sonst steht die Liste still, sobald Ollama aus ist."""
    client.post("/api/settings/begriffe",
                json={"begriff": "ritter", "begriffe": "Knight, Castle"})
    assert not integrations.ollama_enabled()
    assert integrations.suchbegriffe("ritter") == ["Knight", "Castle"]


def test_was_das_modell_liefert_landet_in_der_liste(client, monkeypatch):
    _ki_an(client)
    _ollama(monkeypatch, ["Knight"])
    integrations.suchbegriffe("Ritter")
    begriffe, quelle = integrations.begriffe_gelernt("ritter")
    assert begriffe == ["Knight"] and quelle == "ki"


def test_ein_fehlschlag_wird_nicht_gelernt(client, monkeypatch):
    """Ein leeres Ergebnis ist kein Wissen. Dauerhaft gespeichert stellte es
    den Begriff für immer tot – derselbe Fehler wie beim Zwischenspeicher in
    2.28.0, nur schlimmer, weil er einen Neustart überlebte."""
    _ki_an(client)
    _ollama(monkeypatch, [])
    integrations.suchbegriffe("Kauderwelsch")
    assert integrations.begriffe_gelernt("kauderwelsch") == ([], "")


def test_das_gelernte_ueberlebt_den_neustart(client, monkeypatch):
    """Der Zwischenspeicher ist weg, die Liste bleibt."""
    _ki_an(client)
    gerufen: list = []
    _ollama(monkeypatch, ["Knight"], mitzaehler=gerufen)
    integrations.suchbegriffe("Ritter")
    integrations._begriff_cache.clear()          # wie nach einem Neustart
    assert integrations.suchbegriffe("Ritter") == ["Knight"]
    assert len(gerufen) == 1, "das Modell wurde erneut befragt"


# ------------------------------------------------------------- die Verwaltung

def test_die_liste_zeigt_herkunft_und_sortiert_eigene_nach_oben(client,
                                                                monkeypatch):
    _ki_an(client)
    integrations.begriffe_merken("zauberer", ["Wizard"], "ki")
    client.post("/api/settings/begriffe",
                json={"begriff": "roter c3po", "begriffe": "R-3PO"})

    liste = client.get("/api/settings/begriffe").json()["begriffe"]
    assert [b["quelle"] for b in liste] == ["hand", "ki"]
    assert liste[0]["begriffe"] == ["R-3PO"]


def test_loeschen_wirkt_sofort(client, monkeypatch):
    """Auch im Zwischenspeicher – sonst gälte die gelöschte Zeile weiter,
    und man hielte das Löschen für kaputt."""
    _ki_an(client)
    _ollama(monkeypatch, ["Knight"])
    integrations.suchbegriffe("Ritter")
    assert integrations._begriff_cache.get("ritter") is not None

    client.delete("/api/settings/begriffe/ritter")
    assert integrations.begriffe_gelernt("ritter") == ([], "")
    assert integrations._begriff_cache.get("ritter") is None


def test_leere_eingabe_wird_abgewiesen(client):
    r = client.post("/api/settings/begriffe",
                    json={"begriff": "ritter", "begriffe": "  ,  "})
    assert r.status_code == 400


def test_gross_und_kleinschreibung_egal(client):
    client.post("/api/settings/begriffe",
                json={"begriff": "Roter C3PO", "begriffe": "R-3PO"})
    assert integrations.suchbegriffe("roter c3po") == ["R-3PO"]


def test_nur_fuer_admins(client):
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('gast', 'x', 0, 0, ?)",
                     (now,))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(2, "gast", False)
    assert c.get("/api/settings/begriffe").status_code in (401, 403)
    assert c.post("/api/settings/begriffe",
                  json={"begriff": "x", "begriffe": "y"}
                  ).status_code in (401, 403)


# ------------------------------------------------- Die Liste darf wachsen

def test_die_liste_kommt_seitenweise(client):
    """Sie wächst mit jedem Suchlauf, und ein Durchlauf über die
    BrickLink-Nummern brächte Tausende Zeilen auf einen Schlag. Am Stück
    ausgegeben machte sie die Einstellungen unbenutzbar und die Antwort
    megabyteweise groß."""
    for i in range(40):
        integrations.begriffe_merken("wort%02d" % i, ["Term%02d" % i], "ki")

    d = client.get("/api/settings/begriffe?limit=25").json()
    assert len(d["begriffe"]) == 25
    assert d["gesamt"] == 40 and d["mehr"] is True

    rest = client.get("/api/settings/begriffe?limit=25&offset=25").json()
    assert len(rest["begriffe"]) == 15 and rest["mehr"] is False


def test_gesucht_wird_in_beiden_richtungen(client):
    """„ritter" findet man über den deutschen Begriff, „Knight" über das,
    was dabei herauskommt – wer eine Zeile korrigieren will, weiß mal das
    eine und mal das andere."""
    integrations.begriffe_merken("ritter", ["Knight", "Castle"], "ki")
    integrations.begriffe_merken("pirat", ["Pirate"], "ki")

    assert [b["begriff"] for b in
            client.get("/api/settings/begriffe?q=ritt").json()["begriffe"]] \
        == ["ritter"]
    assert [b["begriff"] for b in
            client.get("/api/settings/begriffe?q=Knight").json()["begriffe"]] \
        == ["ritter"]


def test_die_bilanz_gilt_immer_fuer_alles(client):
    """Sonst sagte „12 eigene" plötzlich etwas anderes, nur weil jemand
    etwas ins Suchfeld getippt hat."""
    integrations.begriffe_merken("ritter", ["Knight"], "ki")
    client.post("/api/settings/begriffe",
                json={"begriff": "roter c3po", "begriffe": "R-3PO"})

    d = client.get("/api/settings/begriffe?q=ritter").json()
    assert d["gefunden"] == 1, "die Suche filtert nicht"
    assert d["gesamt"] == 2 and d["eigene"] == 1


def test_die_einstellungen_zeigen_nur_die_bilanz():
    """Die Liste selbst gehört in ein eigenes Fenster."""
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1]
            / "frontend" / "index.html").read_text(encoding="utf-8")
    i = html.index("Gelernte Begriffe")
    karte = html[i:i + 900]
    assert 'id="begriff-bilanz"' in karte
    assert 'id="begriff-liste"' not in karte, \
        "die vollständige Liste steht wieder in den Einstellungen"
