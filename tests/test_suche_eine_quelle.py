"""Bei Figuren antwortet der eigene Abzug allein.

Svens Beobachtung vom 22.09.2026: „das sind zwei verschiedene Quellen mit
den identischen Ergebnissen". Stimmt – beide kennen dieselben Figuren,
aber unter verschiedenen Nummern (`dis080` hier, `fig-012635` dort) und
mit gleichbedeutenden, nicht gleichen Namen („Qui-Gon Jinn (Yellow Head)"
gegen „Qui-Gon Jinn, Yellow Skin").

Die Entdoppelung vergleicht Nummer plus Typ und kann das nicht fangen.
Eine Brücke gibt es nicht: **Rebrickable liefert für Figuren keine
BrickLink-Nummer**, weder in der Suche noch im Einzelabruf – für Teile
dagegen schon. Also stand jede Figur zweimal da, und die zweite Hälfte
war die schlechtere: ohne Preis, ohne Set-Zugehörigkeit, ohne Nummer.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "quelle.db"))
    core.init_db()
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('sven', 'x', 1, 1, ?)",
                     (int(time.time()),))
    core.set_setting("rebrickable_key", "test-key")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def abzug(*eintraege):
    """Figuren in den eigenen Katalogindex legen."""
    with core.db() as conn:
        for nr, name in eintraege:
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such,"
                " woerter, updated_at) VALUES (?, 'minifig', ?, ?, ?, 0)",
                (nr, name, core.suchtext(name) if hasattr(core, "suchtext")
                 else name.lower().replace(" ", ""), core.suchwoerter(name)))


def zaehlend(monkeypatch, treffer=()):
    """Rebrickable ersetzen und mitzählen, ob es überhaupt gefragt wurde."""
    ruf = {"mal": 0}

    def fake(q, item_type="minifig", page=1, page_size=10):
        ruf["mal"] += 1
        return {"items": [{"item_id": i, "item_type": item_type, "name": n,
                           "img_url": "", "sub": "", "year": 0,
                           "bricklink_url": ""} for i, n in treffer],
                "count": len(treffer), "page": page, "has_more": False}

    monkeypatch.setattr(integrations, "search_catalog", fake)
    return ruf


def test_bei_figuren_wird_rebrickable_gar_nicht_gefragt(client, monkeypatch):
    abzug(("sw0027", "Qui-Gon Jinn Yellow Head"))
    ruf = zaehlend(monkeypatch, [("fig-003614", "Qui-Gon Jinn, Yellow Skin")])
    a = client.get("/api/search?q=qui-gon jinn&item_type=minifig").json()
    nummern = [i["item_id"] for i in a["items"]]
    assert nummern == ["sw0027"], "die Rebrickable-Dublette ist wieder da"
    assert ruf["mal"] == 0, "Rebrickable wurde gefragt, obwohl unnötig"
    assert a["has_more"] is False


def test_ohne_eigenen_treffer_springt_rebrickable_ein(client, monkeypatch):
    """Der Abzug kennt nicht jede brandneue Figur – dann bleibt er die
    zweite Quelle, genau wie vorher."""
    ruf = zaehlend(monkeypatch, [("fig-999999", "Brandneue Figur")])
    a = client.get("/api/search?q=brandneue figur&item_type=minifig").json()
    assert ruf["mal"] == 1, "ohne eigene Treffer muss gefragt werden"
    assert [i["item_id"] for i in a["items"]] == ["fig-999999"]


def test_bei_sets_bleibt_rebrickable_dabei(client, monkeypatch):
    """Dort ist es oft die einzige Quelle – der ausgelieferte Abzug
    enthält nur Figuren."""
    ruf = zaehlend(monkeypatch, [("75192-1", "Millennium Falcon")])
    a = client.get("/api/search?q=millennium falcon&item_type=set").json()
    assert ruf["mal"] == 1
    assert [i["item_id"] for i in a["items"]] == ["75192-1"]


def test_der_farbrueckfall_bleibt_bei_zwanzig(client):
    """Die Ausbeute stieg auf 200 – die Schwelle darf nicht mitwandern.

    Sonst liefe die Verbreiterung praktisch immer, und „gold" hieße wieder
    „yellow": Eine Farbsuche zöge 9.231 Figuren herein.
    """
    import inspect
    quelle = inspect.getsource(main.catalog_search)
    assert "genug=20" in quelle, "die Schwelle ist mitgewandert"
    assert "SUGGEST_MAX if item_type == \"minifig\"" in quelle


def test_die_oberflaeche_blaettert_aus_dem_vorrat():
    """45 Treffer auf einmal hinzustellen wäre keine Liste, sondern eine Wand.

    Der Server gibt bei Figuren alles heraus (bis 200); geblättert wird
    deshalb im Browser, ohne noch einmal zu fragen. Nachgemessen am
    22.09.2026: „stormtrooper" zeigt 10 von 45, und „Weitere Ergebnisse
    laden" löst **keine** neue Anfrage aus.
    """
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js") \
        .read_text(encoding="utf-8")
    assert "function zeigeSuggestSeite" in js
    assert "const SEITE = 10;" in js
    i = js.index("async function loadMoreSuggestions")
    block = js[i:i + 900]
    # Erst der Vorrat, dann erst wieder fragen.
    assert block.index("suggestState.gezeigt < suggestState.items.length") \
        < block.index("api(`/search"), \
        "es wird gefragt, bevor der Vorrat aufgebraucht ist"


# ── Zwei Grenzen, die zusammenpassen müssen ────────────────────────────

def test_oberflaeche_und_server_reichern_gleich_viele_an():
    """Svens Fund vom 22.09.2026 an „gelber Umhang": fünf Karten mit Preis,
    fünf ohne – obwohl BrickLink für alle etwas hat.

    Die Oberfläche schickte acht Nummern zum teuren Abruf, der Server
    bediente davon fünf (`[:5]`). Die drei dazwischen bekamen den Hinweis
    „lade Jahr & Preise …", nie Daten, und am Ende räumte die Oberfläche
    den Hinweis wortlos weg. Solche Fehler sieht man nicht im Code – nur
    in der Liste.
    """
    import re
    from pathlib import Path
    wurzel = Path(__file__).resolve().parents[1]
    js = (wurzel / "frontend" / "app.js").read_text(encoding="utf-8")
    vorne = int(re.search(r"const SUGGEST_DETAIL_MAX = (\d+);", js).group(1))
    assert vorne == main.SUGGEST_DETAIL_MAX, (
        f"Oberfläche fragt {vorne} an, Server reichert "
        f"{main.SUGGEST_DETAIL_MAX} an")
    seite = int(re.search(r"const SEITE = (\d+);", js).group(1))
    assert vorne == seite, (
        "jede angezeigte Karte soll Daten bekommen – sonst sieht eine "
        "halbe Seite aus wie kaputt")


def test_der_server_deckelt_die_teuren_abrufe(client, monkeypatch):
    """Ohne Deckel zöge eine Suche beliebig viel BrickLink-Kontingent."""
    gerufen = []

    def teuer(item_type, item_no, *a, **k):
        gerufen.append(item_no)
        return {"avg": "1.00"}

    monkeypatch.setattr(main.integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(main.integrations, "price_guide", teuer)
    monkeypatch.setattr(main.integrations, "bricklink_item",
                        lambda *a, **k: {"year": 2020})
    monkeypatch.setattr(main, "_fig_sets_cached", lambda *a, **k: [])
    viele = [{"item_id": "sw%04d" % i, "item_type": "minifig"}
             for i in range(30)]
    client.post("/api/suggest_info?detail=1", json={"items": viele})
    assert len(set(gerufen)) <= main.SUGGEST_DETAIL_MAX
