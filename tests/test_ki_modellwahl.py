"""Das Modell aussuchen statt abtippen.

Der Modellname musste exakt so eingetragen werden, wie Ollama ihn führt –
`qwen2.5:14b`, nicht `qwen2.5-14b` und nicht `qwen 2.5`. Ein Tippfehler sah
dabei aus wie ein kaputter Dienst: Die Verbindung stand, nur das Modell gab
es nicht. Auf Svens Server liegen 14 Stück, darunter `qwen2.5:14b` **und**
`qwen2.5:14b-instruct` – die Verwechslung ist keine Theorie.

Die Liste ist eine Bequemlichkeit, kein Zugangsweg: Schweigt der Dienst,
bleibt das Textfeld, und wer den Namen kennt, trägt ihn weiter von Hand ein.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "mw.db"))
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


def _tags(monkeypatch, modelle, gefragt=None):
    """`/api/tags` vortäuschen – in der Form, die Ollama wirklich liefert."""
    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"models": [{"name": m, "model": m, "size": 1,
                                "details": {}} for m in modelle]}

    def fake_get(url, **kw):
        if gefragt is not None:
            gefragt.append(url)
        return Fake()

    monkeypatch.setattr(integrations.requests, "get", fake_get)


def test_die_modelle_des_servers_stehen_zur_wahl(client, monkeypatch):
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": "qwen2.5:14b"})
    _tags(monkeypatch, ["qwen2.5:14b", "gemma3:12b"])

    d = client.get("/api/settings/ollama/models").json()
    assert d["models"] == ["gemma3:12b", "qwen2.5:14b"]   # alphabetisch
    assert d["current"] == "qwen2.5:14b"


def test_eine_noch_nicht_gespeicherte_adresse_laesst_sich_abfragen(
        client, monkeypatch):
    """Sonst müsste man erst eine ungeprüfte Einstellung sichern, um zu
    sehen, was dort überhaupt zur Wahl steht."""
    gefragt = []
    _tags(monkeypatch, ["llava:latest"], gefragt)

    d = client.get("/api/settings/ollama/models"
                   "?url=http://192.168.0.99:11434").json()
    assert d["models"] == ["llava:latest"]
    assert gefragt and gefragt[0].startswith("http://192.168.0.99:11434")


def test_adresse_muss_ein_schema_haben(client):
    r = client.get("/api/settings/ollama/models?url=192.168.0.99:11434")
    assert r.status_code == 400


def test_ohne_adresse_wird_nichts_gefragt(client, monkeypatch):
    gefragt = []
    _tags(monkeypatch, ["egal"], gefragt)
    d = client.get("/api/settings/ollama/models").json()
    assert d["models"] == []
    assert gefragt == [], "es wurde ins Leere gefragt"


def test_ein_stummer_dienst_gibt_eine_leere_liste(client, monkeypatch):
    """Kein Fehler: Die Auswahl ist eine Bequemlichkeit. Fällt sie aus, muss
    das Textfeld übernehmen – sonst käme man an kein Modell mehr."""
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": ""})

    def kaputt(*a, **k):
        raise integrations.requests.RequestException("weg")
    monkeypatch.setattr(integrations.requests, "get", kaputt)

    r = client.get("/api/settings/ollama/models")
    assert r.status_code == 200
    assert r.json()["models"] == []


def test_doppelte_namen_nur_einmal(client, monkeypatch):
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": ""})
    _tags(monkeypatch, ["qwen2.5:14b", "qwen2.5:14b", "gemma3:12b"])
    assert client.get("/api/settings/ollama/models").json()["models"] == \
        ["gemma3:12b", "qwen2.5:14b"]


def test_nur_fuer_admins(client, monkeypatch, tmp_path):
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('gast', 'x', 0, 0, ?)",
                     (now,))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(2, "gast", False)
    assert c.get("/api/settings/ollama/models").status_code in (401, 403)


# ------------------------------------------------------------- Oberfläche

def _js():
    from pathlib import Path
    return (Path(__file__).resolve().parents[1]
            / "frontend" / "app.js").read_text(encoding="utf-8")


def test_das_gespeicherte_modell_bleibt_waehlbar(monkeypatch):
    """Liegt es nicht mehr auf dem Server, gehört es trotzdem in die Liste –
    sonst überschriebe ein Speichern still eine noch gültige Einstellung."""
    js = _js()
    i = js.index("async function modelleLaden(")
    block = js[i:js.index("function modellwahlGeaendert(")]
    assert "nicht auf dem Server" in block


def test_ohne_liste_uebernimmt_das_textfeld(monkeypatch):
    js = _js()
    i = js.index("async function modelleLaden(")
    block = js[i:js.index("function modellwahlGeaendert(")]
    # Beide Ausfälle – Fehler und leere Liste – müssen das Feld zeigen.
    assert block.count("frei.hidden = false") >= 2


def test_gespeichert_wird_was_wirklich_gewaehlt_ist(monkeypatch):
    """Ist die Liste verborgen oder „anderes Modell" gewählt, zählt das
    Textfeld – sonst landete `__frei__` als Modellname in der Datenbank."""
    js = _js()
    i = js.index("function ollamaModell(")
    block = js[i:i + 400]
    assert 'wahl.hidden || wahl.value === "__frei__"' in block
    assert "saveOllama" in js and "model: ollamaModell()" in js


# ------------------------------------------- Nur die sinnvollen zur Wahl

def test_code_modelle_stehen_nicht_zur_wahl(client, monkeypatch):
    """Sie taugen für keine der beiden Aufgaben und stünden sonst mitten in
    einer Liste, in der man das Passende suchen soll."""
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": ""})
    _tags(monkeypatch, ["qwen2.5:14b", "qwen3-coder:30b", "codellama:13b",
                        "gemma3:12b"])
    d = client.get("/api/settings/ollama/models").json()
    assert d["models"] == ["gemma3:12b", "qwen2.5:14b"]


def test_bildfaehige_werden_gemeldet_aber_nicht_erzwungen(client, monkeypatch):
    """`gemma3:12b` meldet kein `vision` und ist trotzdem das beste im Haus
    (gemessen 21.08.2026). Wer hart nach dem Merkmal filtert, versteckt den
    Sieger – deshalb wird es nur mitgeliefert, zum Sortieren."""
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": ""})

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"models": [
                {"name": "gemma3:12b", "capabilities": ["completion"]},
                {"name": "minicpm-v:latest",
                 "capabilities": ["completion", "vision"]}]}
    monkeypatch.setattr(integrations.requests, "get",
                        lambda url, **kw: Fake())

    d = client.get("/api/settings/ollama/models").json()
    assert d["models"] == ["gemma3:12b", "minicpm-v:latest"], "es wurde gefiltert"
    assert d["vision"] == ["minicpm-v:latest"]


def test_die_oberflaeche_sortiert_statt_zu_filtern():
    js = _js()
    i = js.index("const sieht = new Set(")
    block = js[i:i + 400]
    assert "sort(" in block, "die Liste wird nicht sortiert"
    assert "filter(" not in block, "die Liste wird gefiltert statt sortiert"


# ------------------------------------------------- Denkmodelle antworten anders

def test_die_antwort_wird_auch_aus_dem_denkfeld_gelesen(client, monkeypatch):
    """`qwen3-vl` ist ein Denkmodell: Es legt seine Antwort in `thinking` ab,
    `content` bleibt leer, und `think: false` ändert daran nichts (geprüft
    21.08.2026). Ohne diesen Griff sah ausgerechnet das beste Bildmodell im
    Haus aus, als könne es gar nichts – dabei stand die richtige Antwort da,
    nur im falschen Feld."""
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": "denker"})

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "",
                                "thinking": '{"begriffe": ["Knight"]}'}}
    monkeypatch.setattr(integrations.requests, "post",
                        lambda url, **kw: Fake())
    assert integrations.suchbegriffe("Ritter") == ["Knight"]


def test_content_hat_vorrang_vor_dem_denkfeld(client, monkeypatch):
    """Das Denkfeld ist der Notnagel, nicht die Quelle: Wo beides steht,
    zählt die eigentliche Antwort."""
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": "denker"})

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": '{"begriffe": ["Knight"]}',
                                "thinking": '{"begriffe": ["Unsinn"]}'}}
    monkeypatch.setattr(integrations.requests, "post",
                        lambda url, **kw: Fake())
    assert integrations.suchbegriffe("Ritter") == ["Knight"]


def test_auch_die_farben_kommen_aus_dem_denkfeld(client, monkeypatch):
    client.post("/api/settings/ollama",
                json={"url": "http://127.0.0.1:11434", "model": "denker"})

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "thinking":
                                '{"art": "Droide", "farben": ["rot"]}'}}
    monkeypatch.setattr(integrations.requests, "post",
                        lambda url, **kw: Fake())
    m = integrations.bild_merkmale(b"BILD")
    assert m == {"art": "droide", "farben": ["rot"]}
