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


# ── Breite Wörter aus der Bildbeschreibung ────────────────────────────
#
# Das Sehmodell beschreibt **jede** Figur Teil für Teil. Gemessen am
# 21.09.2026 an 19.267 Figuren: `torso` steht in 19.266 Beschreibungen,
# `legs` in 19.188, `yellow` in 13.209 – im Namen dagegen nur 833, 5.801
# und 1.155 Mal. Wer „gelb" suchte, bekam zwei Drittel des Katalogs.
#
# Sven hat die Regel dafür gesetzt: Ein gelber Kopf *ist* gelb, und das
# soll auch zu finden sein – aber nur, wenn man nach dem gelben **Kopf**
# fragt, nicht bei „gelb" allein.

def _viele_mit_merkmalen(anzahl=250):
    """So viele Zeilen, dass die Regel überhaupt greift."""
    with core.db() as conn:
        for i in range(anzahl):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such,"
                " woerter, farben, merkmale, updated_at)"
                " VALUES (?, 'minifig', ?, ?, ?, ?, ?, 0)",
                ("fig%04d" % i, "Figur %d" % i,
                 core.wortanfaenge("Figur %d" % i)[0],
                 core.suchwoerter("Figur %d" % i), "",
                 "head yellow eyes; torso blue shirt"))


def test_ein_einzelnes_breites_wort_zieht_nicht_den_ganzen_katalog(client):
    """`torso` steht in jeder Beschreibung – allein sagt es nichts.

    Bei **Farben** greift ohnehin schon die Farbliste (`_farbrang`): Wer
    „gelb" sucht, bekommt nur Figuren, die das Sehmodell insgesamt als gelb
    sieht. Bei Körperteilen gab es diese Bremse nicht, und `torso` traf
    19.266 von 19.267 Figuren.
    """
    _viele_mit_merkmalen()
    main._merkmal_breit = ()          # Zwischenspeicher verwerfen
    assert main._katalog_lauf_suchen("torso", 50, "minifig") == []


def test_im_verbund_zaehlt_die_beschreibung_sehr_wohl(client):
    """Der blaue Torso ist zu finden – man muss ihn nur meinen.

    Svens Regel: Die Auskunft aus dem Bild ist richtig und soll bleiben;
    sie darf nur nicht auf ein einzelnes Allerweltswort anspringen.
    """
    _viele_mit_merkmalen()
    main._merkmal_breit = ()
    assert len(main._katalog_lauf_suchen("torso shirt", 50, "minifig")) > 0


def test_bei_wenigen_zeilen_gilt_keine_beschraenkung(client):
    """Sonst entwertet die Regel bei einer jungen Instanz die Bildanalyse."""
    with core.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " woerter, farben, merkmale, updated_at)"
            " VALUES ('sw0021', 'minifig', 'Luke', 'luke', ' luke ', '',"
            " 'torso white tunic', 0)")
    main._merkmal_breit = ()
    assert [t["item_id"] for t in
            main._katalog_lauf_suchen("tunic", 20, "minifig")] == ["sw0021"]


def test_deutsche_farben_unterliegen_derselben_pruefung(client):
    """Sonst ist „helm weiss" lockerer als „helmet white".

    Die Farbprüfung verlangt, dass die Farbe die Figur beschreibt und nicht
    nur ein Detail. Deutsche Farbwörter standen nicht in `FARBWOERTER` –
    damit entfiel sie stillschweigend, und die deutsche Anfrage fand mehr
    als die englische. Gemessen am 21.09.2026: 76 gegen 51 Treffer, und der
    ganze Unterschied war diese fehlende Prüfung.
    """
    _katalog([("w0001", "Knight", "black")])
    with core.db() as conn:
        conn.execute("UPDATE katalog_index SET merkmale = ? WHERE item_no = ?",
                     ("helm weiss mit visier", "w0001"))
    main._merkmal_breit = ()
    # Die Figur ist schwarz – ein weißer Helm macht sie nicht weiß.
    assert main._katalog_lauf_suchen("weiss helm", 20, "minifig") == []
    assert main._katalog_lauf_suchen("white helmet", 20, "minifig") == []
