"""„Roter c3po" fand im Katalog nichts, obwohl die KI eingerichtet war.

2.28.0 hat die Übersetzung an die **Sammlungssuche** gehängt. Sven hat sie
am 20.08.2026 dort ausprobiert, wo man sie zuerst vermutet: im Feld „Name"
unter „✏️ Manuell erfassen". Das sucht im **Katalog** (Rebrickable), und
dort gab es die Übersetzung nicht – die Suche blieb leer, und von außen sah
das aus, als funktioniere die KI nicht.

Dabei ist der Katalog der Ort, an dem es am meisten hilft: In der eigenen
Sammlung kann man notfalls blättern, im Katalog sucht man Unbekanntes.
Findet man nichts, hat man gar nichts.

Wie in der Sammlung gilt: Das Modell liefert **Suchbegriffe, niemals
Ergebnisse**. Jede Zeile kommt weiter von Rebrickable; ein erfundener
Begriff findet dort schlicht nichts.
"""
import time

import pytest

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
    core.set_setting("rebrickable_key", "test-key")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def _ollama(monkeypatch, antwort):
    import json as json_mod

    class Fake:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content":
                                json_mod.dumps({"begriffe": antwort})}}

    monkeypatch.setattr(integrations.requests, "post",
                        lambda url, **kw: Fake())


def _katalog(monkeypatch, treffer_je_begriff, gefragt=None):
    """Rebrickable vortäuschen: je Suchbegriff eine Trefferliste."""
    def fake_search(query, item_type="minifig", page=1, page_size=10):
        if gefragt is not None:
            gefragt.append(query)
        namen = treffer_je_begriff.get(query, [])
        return {"items": [{"item_id": "sw%04d" % i, "item_type": "minifig",
                           "name": n, "img_url": "", "bricklink_url": "",
                           "year": 0} for i, n in enumerate(namen)],
                "count": len(namen), "page": 1, "has_more": False}
    monkeypatch.setattr(integrations, "search_catalog", fake_search)


def _einrichten(client):
    r = client.post("/api/settings/ollama",
                    json={"url": "http://127.0.0.1:11434", "model": "test"})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------- der Vorfall

def test_deutsche_eingabe_findet_den_englischen_katalogeintrag(client,
                                                               monkeypatch):
    """Der Fall aus dem Bild: „Roter c3po" muss den roten C-3PO finden."""
    _einrichten(client)
    _ollama(monkeypatch, ["C-3PO", "C-3PO red"])
    _katalog(monkeypatch, {"C-3PO red": ["C-3PO - Dark Red Arm"],
                           "C-3PO": ["C-3PO"]})

    r = client.get("/api/search/suggest?q=Roter%20c3po")
    assert r.status_code == 200, r.text
    daten = r.json()
    assert "C-3PO - Dark Red Arm" in [i["name"] for i in daten["items"]]


def test_der_genaueste_begriff_kommt_zuerst(client, monkeypatch):
    """Dieselbe Reihenfolge wie in der Sammlung: nach Wortzahl, nicht nach
    Länge. Sonst liefe der breite Begriff zuerst und sammelte alles ein,
    bevor die Eingrenzung drankommt."""
    _einrichten(client)
    gefragt = []
    _ollama(monkeypatch, ["C-3PO", "C-3PO red"])
    _katalog(monkeypatch, {"C-3PO red": ["C-3PO - Dark Red Arm"],
                           "C-3PO": ["C-3PO"]}, gefragt)

    client.get("/api/search/suggest?q=Roter%20c3po")
    assert gefragt[0] == "C-3PO red", "der breite Begriff lief zuerst"


def test_nur_begriffe_mit_treffern_werden_genannt(client, monkeypatch):
    """Ein erfundener Begriff darf nicht im Hinweis stehen – sonst sieht es
    aus, als hätte er etwas beigetragen."""
    _einrichten(client)
    _ollama(monkeypatch, ["Knight", "Medieval Figure"])
    _katalog(monkeypatch, {"Knight": ["Castle Knight"], "Medieval Figure": []})

    daten = client.get("/api/search/suggest?q=Ritter").json()
    assert daten["begriffe"] == ["Knight"]


def test_hoechstens_zwei_anfragen_an_rebrickable(client, monkeypatch):
    """Jeder Versuch ist hier eine eigene Anfrage an einen fremden Dienst –
    anders als in der Sammlung, wo die Einträge schon im Speicher liegen.
    Aus einer Suche dürfen nicht fünf werden."""
    _einrichten(client)
    gefragt = []
    _ollama(monkeypatch, ["A", "B", "C", "D", "E"])
    _katalog(monkeypatch, {}, gefragt)

    client.get("/api/search/suggest?q=irgendwas")
    assert len(gefragt) <= main.KATALOG_KI_VERSUCHE, gefragt


def test_ohne_eingerichtete_ki_passiert_nichts(client, monkeypatch):
    _katalog(monkeypatch, {"Knight": ["Castle Knight"]})
    daten = client.get("/api/search/suggest?q=Ritter").json()
    assert daten == {"begriffe": [], "items": []}


def test_ohne_katalogzugang_passiert_nichts(client, monkeypatch):
    """Ohne Rebrickable-Schlüssel gibt es nichts zu durchsuchen – dann soll
    auch das Modell nicht bemüht werden."""
    _einrichten(client)
    core.set_setting("rebrickable_key", "")
    gefragt = []
    _ollama(monkeypatch, ["Knight"])
    _katalog(monkeypatch, {"Knight": ["Castle Knight"]}, gefragt)

    daten = client.get("/api/search/suggest?q=Ritter").json()
    assert daten == {"begriffe": [], "items": []}
    assert gefragt == [], "Rebrickable wurde trotzdem gefragt"


def test_ein_stoerender_katalog_beendet_die_suche_nicht_mit_fehler(
        client, monkeypatch):
    """Der Zusatzversuch ist eine Zugabe. Antwortet Rebrickable nicht, bleibt
    es bei der leeren Liste von vorher – kein Fehler, kein roter Kasten."""
    _einrichten(client)
    _ollama(monkeypatch, ["Knight"])

    def kaputt(*a, **k):
        raise integrations.requests.RequestException("weg")
    monkeypatch.setattr(integrations, "search_catalog", kaputt)

    r = client.get("/api/search/suggest?q=Ritter")
    assert r.status_code == 200
    assert r.json() == {"begriffe": [], "items": []}


def test_jede_zeile_nur_einmal(client, monkeypatch):
    """Zwei Begriffe können denselben Katalogeintrag finden."""
    _einrichten(client)
    _ollama(monkeypatch, ["C-3PO", "C-3PO red"])
    _katalog(monkeypatch, {"C-3PO red": ["C-3PO"], "C-3PO": ["C-3PO"]})

    items = client.get("/api/search/suggest?q=Roter%20c3po").json()["items"]
    kennungen = [(i["item_id"], i["item_type"]) for i in items]
    assert len(kennungen) == len(set(kennungen))


def test_die_oberflaeche_fragt_erst_nach_einer_leeren_suche(client):
    """Sonst liefe bei jedem Tastendruck eine Modellanfrage mit."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1]
          / "frontend" / "app.js").read_text(encoding="utf-8")
    i = js.index("async function runCatalogSearch(")
    block = js[i:js.index("async function katalogKiVersuch(")]
    # Seit 2.52.0 auch dann, wenn nur Rebrickable etwas fand: Es rät
    # unscharf, und „ritter" lieferte von dort `Miss Fritter` – ein
    # Ergebnis, das `Knight` verhinderte.
    assert "suggestState.items.length || suggestState.eigeneLeer" in block
    assert "katalogKiVersuch(q, type, seq, hint)" in block


# ------------------------------------------------- Eine Suche endet nie stumm

def _js():
    from pathlib import Path
    return (Path(__file__).resolve().parents[1]
            / "frontend" / "app.js").read_text(encoding="utf-8")


def _katalogsuche():
    js = _js()
    i = js.index("async function runCatalogSearch(")
    return js[i:js.index("function nichtsGefundenHinweis(")]


def test_die_nichts_gefunden_meldung_wird_nicht_gleich_wieder_geloescht():
    """`renderSuggestions` setzt bei leerer Liste selbst „Nichts gefunden …".

    Eine Zeile später stand `hint.hidden = true` – pauschal, ohne Ansehen des
    Ergebnisses. Damit war die Meldung weg, kaum dass sie da war: Wer nichts
    fand, sah nicht einmal, dass gesucht worden war. Aufgefallen am
    21.08.2026 beim manuellen Erfassen.
    """
    block = _katalogsuche()
    assert "if (suggestState.items.length) hint.hidden = true;" in block, \
        "der Hinweis wird weiterhin pauschal ausgeblendet"


def test_jeder_ausgang_des_ki_versuchs_hinterlaesst_eine_meldung():
    """Fehlschlag und leeres Ergebnis blendeten den Hinweis aus – dann stand
    gar nichts mehr da, und man wusste nicht, ob noch gesucht wird."""
    js = _js()
    i = js.index("async function katalogKiVersuch(")
    block = js[i:js.index("async function loadMoreSuggestions(")]
    assert block.count("nichtsGefundenHinweis(hint)") >= 2
    assert "hint.hidden = true" not in block, \
        "es gibt weiterhin einen stummen Ausgang"


def test_ohne_katalogzugang_sagt_die_oberflaeche_warum():
    """Vorher tippte man und es passierte sichtbar nichts – ununterscheidbar
    von „findet nichts" und von „ist kaputt"."""
    assert "Katalogsuche ist nicht eingerichtet" in _katalogsuche()


# ------------------------------- Wer „Set" einstellt, will kein Minifig

def test_bei_typ_set_kommt_keine_figur_aus_dem_eigenen_index(client,
                                                             monkeypatch):
    """Svens Fall vom 21.08.2026: Oben stand „Set", gesucht war die UCS
    Razor Crest – heraus kam „Clone ARF Trooper Razor", eine Figur.

    Der eigene Katalogindex enthält ausschließlich Figuren, wurde aber ohne
    Rücksicht auf den eingestellten Typ befragt. Schlimmer noch: Fand er
    etwas, kehrte die Suche vorzeitig zurück – die eigentliche Set-Suche
    fand danach gar nicht mehr statt.
    """
    _einrichten(client)
    with core.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " updated_at) VALUES ('sw0297', 'minifig',"
            " 'Clone ARF Trooper Razor / Stak, 91st Mobile Recon', "
            " 'clone arf trooper razor stak 91st mobile recon', 0)")
    _ollama(monkeypatch, ["Razor"])
    gefragt = []
    _katalog(monkeypatch, {"Razor": ["Razor Crest UCS"]}, gefragt)

    d = client.get("/api/search/suggest?q=UCS%20Razor%20crest"
                   "&item_type=set").json()
    namen = [i["name"] for i in d["items"]]
    assert not any("Clone ARF Trooper" in n for n in namen), \
        "eine Figur, obwohl „Set“ eingestellt war"
    assert gefragt, "die eigentliche Set-Suche fand gar nicht statt"
    assert "Razor Crest UCS" in namen


def test_bei_typ_minifig_bleibt_der_index_die_erste_wahl(client, monkeypatch):
    """Die Gegenprobe: Für Figuren soll er weiter zuerst greifen – er kostet
    nichts und kennt die beschreibenden Namen, die Rebrickable nicht hat."""
    _einrichten(client)
    with core.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " updated_at) VALUES ('sw0297', 'minifig',"
            " 'Clone ARF Trooper Razor', 'clone arf trooper razor', 0)")
    _ollama(monkeypatch, ["Razor"])
    gefragt = []
    _katalog(monkeypatch, {"Razor": ["Irgendwas von Rebrickable"]}, gefragt)

    # Nicht „Razor" selbst fragen: Ein Begriff, der der Eingabe gleicht,
    # gilt als keine Übersetzung und fällt vorher heraus.
    d = client.get("/api/search/suggest?q=Klonsoldat%20Razor"
                   "&item_type=minifig").json()
    assert [i["name"] for i in d["items"]] == ["Clone ARF Trooper Razor"]
    assert gefragt == [], "Rebrickable wurde unnötig gefragt"


# ------------------------- Die Sammlung lässt Bilder los, die keiner sieht

def _app_js():
    import pathlib
    return (pathlib.Path(__file__).resolve().parent.parent
            / "frontend" / "app.js").read_text(encoding="utf-8")


def test_die_sammlung_laesst_bilder_ausserhalb_des_blicks_los():
    """Die Sammlung lädt beim Scrollen nach und räumte nie auf. Der
    Fehlerbericht vom 28.08.2026 zeigt den Endstand vor dem Absturz:
    15.033 Elemente und **844 Bilder**, dann war der Renderer tot – bei
    11 MB gemeldetem Speicher, weil entpackte Bilder nicht dazuzählen."""
    quelle = _app_js()
    assert "function bildFreigeben(" in quelle
    # Der Beobachter muss **jede** Karte sehen, nicht nur die mit Hintergrund.
    assert 'root.querySelectorAll(".card").forEach' in quelle
    assert "bildFreigeben(e.target, e.isIntersecting)" in quelle


def test_die_karte_selbst_bleibt_stehen():
    """Entfernen verschöbe die Scrollposition und verlöre den aufgeklappten
    Zustand – getauscht wird nur die Bildquelle."""
    quelle = _app_js()
    block = quelle[quelle.index("function bildFreigeben("):]
    block = block[:block.index("\n}\n")]
    assert "remove()" not in block and "innerHTML" not in block
    assert "img.dataset.src" in block


def test_der_nachschub_meldet_jede_karte_an():
    """`hintergrundBeobachten` läuft, **bevor** die Karten im Dokument
    stehen – dort findet `querySelectorAll` nichts. Angemeldet werden sie
    im Nachschub, und der nahm nur Karten mit `data-bg`. Ergebnis: 27 von
    63 Karten waren weit aus dem Blick und keine einzige freigegeben
    (28.08.2026, live gemessen)."""
    quelle = _app_js()
    assert "if (bgBeobachter) bgBeobachter.observe(c);" in quelle
    assert "if (bgBeobachter && c.dataset.bg)" not in quelle
