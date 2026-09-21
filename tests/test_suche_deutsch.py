"""Deutsche Suche ohne KI – Wörterbuch, Wortformen, Vorauswahl.

Die Katalognamen sind englisch. Wer „roter Ritter" tippt, fand bis 2.80.3
nur etwas, wenn ein lokales Sprachmodell eingerichtet war. Diese Proben
halten fest, was seitdem **ohne** Modell funktioniert – und die beiden
Fehler, die der erste Trainingslauf am 21.09.2026 ausgegraben hat.
"""
import time

import pytest

import core
import integrations
import main
import woerterbuch
from fastapi.testclient import TestClient


# ── Das Wörterbuch ────────────────────────────────────────────────────

def test_einfache_woerter():
    assert woerterbuch.nachschlagen("ritter") == ("knight",)
    assert woerterbuch.nachschlagen("umhang") == ("cape",)
    assert "gray" in woerterbuch.nachschlagen("grau")


def test_endungen_fallen_ab():
    """„Ritters", „Droiden", „blaue" sind dasselbe Wort."""
    assert woerterbuch.nachschlagen("ritters") == ("knight",)
    assert woerterbuch.nachschlagen("droiden") == ("droid",)
    assert woerterbuch.nachschlagen("blaue") == ("blue",)


def test_umlaute_in_beiden_schreibweisen():
    assert woerterbuch.nachschlagen("könig") == woerterbuch.nachschlagen("koenig")
    assert woerterbuch.nachschlagen("mütze") == woerterbuch.nachschlagen("muetze")


def test_zusammengesetzte_woerter_werden_zerlegt():
    """Der Teil, an dem eine reine Wortliste sonst scheitert."""
    assert woerterbuch.nachschlagen("protokolldroide") == ("protocol", "droid")
    assert woerterbuch.nachschlagen("sturmtruppler") == ("storm", "trooper")
    assert woerterbuch.nachschlagen("piratenkapitaen") == ("pirate", "captain")
    # Mit Fugen-s
    assert woerterbuch.nachschlagen("arbeitshose")[0] == "work"


def test_unbekanntes_bleibt_stehen():
    """Eigennamen sind schon englisch – sie dürfen nicht verschwinden."""
    assert woerterbuch.uebersetzen("roter windu") == ["red windu"]


def test_ohne_ein_einziges_treffendes_wort_kommt_nichts():
    assert woerterbuch.uebersetzen("windu skywalker") == []


def test_mehrere_entsprechungen_geben_mehrere_fassungen():
    fassungen = woerterbuch.uebersetzen("grauer helm")
    assert fassungen[0] == "gray helmet"
    assert "bluish gray helmet" in fassungen


# ── Umlaute im Suchtext ───────────────────────────────────────────────

def test_umlaute_sind_keine_trennzeichen():
    """Bis 2.80.3 zerfiel „Mütze" in „m" + „tze" – der Rest war Zufall."""
    assert core.wortanfaenge("Mütze")[0] == "muetze"
    assert core.wortanfaenge("König")[0] == "koenig"
    assert core.wortanfaenge("Fußball")[0] == "fussball"
    # Englische Namen bleiben unberührt
    assert core.wortanfaenge("C-3PO")[0] == "c3po"


def test_suchwoerter_trennt_mit_leerzeichen():
    assert core.suchwoerter("Crown King with Plume") == " crown king with plume "


# ── Die Vorauswahl ────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "suche.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (now,))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


def _katalog(zeilen):
    with core.db() as conn:
        for nr, name, farben in zeilen:
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such,"
                " woerter, farben, updated_at) VALUES (?, 'minifig', ?, ?, ?,"
                " ?, 0)",
                (nr, name, core.wortanfaenge(name)[0],
                 core.suchwoerter(name), farben))


def test_wortanfang_statt_irgendwo(client):
    """**Der Fehler, der „king" unfindbar machte.**

    `such` klebte alle Wörter aneinander, und die Vorauswahl nahm die
    ersten 400 Zeilen. „Markings" und „Parking" füllten sie, bevor ein
    echter König an der Reihe war.
    """
    _katalog([("x%04d" % i, "Clone Trooper Yellow Markings %d" % i, "")
              for i in range(50)]
             + [("k0001", "Crown King with Plume", "gold")])
    treffer = main._katalog_lauf_suchen("king", 20, "minifig")
    assert [t["item_id"] for t in treffer] == ["k0001"]


def test_jedes_wort_zaehlt_in_der_vorauswahl(client):
    """**Der zweite Fehler:** gefiltert wurde nur über das längste Wort.

    Bei „schwarzer ninja" war das „black" – und die Grenze von 400 war
    erreicht, bevor der erste Ninja kam.
    """
    _katalog([("b%04d" % i, "Black Suit Guy %d" % i, "black")
              for i in range(50)]
             + [("n0001", "Ninja Skullbreaker", "black")])
    treffer = main._katalog_lauf_suchen("black ninja", 20, "minifig")
    assert [t["item_id"] for t in treffer] == ["n0001"]


def test_deutsche_anfrage_findet_ohne_modell(client, monkeypatch):
    """Der ganze Weg: deutsch rein, englischer Katalog, kein Ollama."""
    monkeypatch.setattr(integrations, "ollama_enabled", lambda: False)
    _katalog([("r0001", "Crown King with Plume", "gold"),
              ("r0002", "Battle Droid - Red", "red")])
    fassungen = integrations.suchbegriffe("könig")
    assert "king" in fassungen
    treffer = main._katalog_lauf_suchen(fassungen[0], 20, "minifig")
    assert [t["item_id"] for t in treffer] == ["r0001"]


def test_von_hand_gepflegtes_schlaegt_die_liste(client):
    """Was jemand eingetragen hat, gilt – auch gegen das Wörterbuch."""
    integrations.begriffe_merken("ritter", ["jedi"], quelle="hand")
    assert integrations.suchbegriffe("ritter") == ["jedi"]
