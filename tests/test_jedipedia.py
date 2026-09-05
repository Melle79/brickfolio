"""Der optionale Verweis ins deutsche Star-Wars-Wiki.

Drei Dinge sind dabei leicht falsch gemacht:

- Direkt zu verlinken statt zu suchen. Der Katalog ist englisch, die
  Jedipedia deutsch: „Battle Droid" heißt dort „Kampfdroide", und
  `/wiki/Battle_Droid` wäre eine tote Adresse.
- Den Verweis überall zu zeigen. Das Wiki kennt nur Star Wars; bei einer
  City-Figur wäre er eine leere Trefferliste.
- Ihn ungefragt einzuschalten. Es ist ein Weg nach draußen aus einer App,
  die sonst vollständig im eigenen Netz läuft.
"""
import re
import time
from pathlib import Path

import pytest

import core
import main
from fastapi.testclient import TestClient

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def _fn(name):
    m = re.search(r"function %s\([^)]*\) \{.*?\n\}\n" % name,
                  APP_JS.read_text(), re.S)
    assert m, "%s nicht gefunden" % name
    return m.group(0)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "jp.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('sven', 'x', 1, ?)", (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_ausgeschaltet_voreingestellt(client):
    """Ein Weg nach draußen gehört nicht ungefragt in die App."""
    assert client.get("/api/config").json()["jedipedia"] is False


def test_der_schalter_haelt(client):
    client.post("/api/settings/jedipedia", json={"an": True})
    assert client.get("/api/config").json()["jedipedia"] is True
    client.post("/api/settings/jedipedia", json={"an": False})
    assert client.get("/api/config").json()["jedipedia"] is False


def test_der_verweis_raet_keinen_artikelpfad():
    """Aus dem Katalognamen darf **nie** ein Artikelpfad gebaut werden:
    `/wiki/Battle_Droid` wäre tot. Ein Artikelpfad entsteht nur aus der
    nachgeschlagenen Tabelle, sonst bleibt es bei der Suche."""
    quelle = APP_JS.read_text()
    assert "Spezial:Suche?search=" in quelle
    z = _fn("jedipediaZiel")
    assert "JEDIPEDIA_TITEL[begriff]" in z
    # Der Artikelzweig hängt am Tabellentreffer, nicht am Begriff.
    kopf, rest = z.split("if (titel)", 1)
    assert "JEDIPEDIA_ARTIKEL" not in kopf
    assert "JEDIPEDIA_ARTIKEL + encodeURIComponent(titel" in rest


def test_nur_bei_star_wars():
    f = _fn("jedipediaLink")
    assert "istStarWars(" in f
    g = _fn("istStarWars")
    # `swtv` gehört dazu, `cty` nicht.
    assert "sw(tv)?" in g


def test_die_variante_faellt_weg():
    """„Boba Fett - Classic Grays" – gesucht wird die Figur, nicht ihre
    Bemalung."""
    f = _fn("jedipediaBegriff")
    assert '" - "' in f
    assert "replace" in f


def test_ohne_zustimmung_kein_verweis():
    f = _fn("jedipediaLink")
    assert "state.jedipedia" in f
    assert f.index("state.jedipedia") < f.index("return `")


# ── Nachschlagen statt suchen ──────────────────────────────────────────
#
# Am 05.09.2026 gemeldet: „Bei vielen kommt nur die Suchseite raus."
# Nachgemessen an Svens 563 Star-Wars-Figuren landeten nur 151 im Artikel.
# Der Rest scheiterte an drei Dingen: englische Gattungsnamen, für die das
# Wiki einen deutschen Titel führt; weggeworfene Klammern, in denen die
# Kennung stand; und Kandidaten, die auf Sammelartikel zeigten.

import json
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import jedipedia_titel as jt                                    # noqa: E402

TABELLE = Path(__file__).resolve().parents[1] / "frontend" / "jedipedia-titel.js"

# Echte Katalognamen, jeder mit seiner Eigenheit.
NAMEN = [
    "Assassin Droid (IG-88) - Dark Bluish Gray, Printed Head",
    "Astromech Droid, C1-10P (Chopper) - White Body",
    "Boba Fett - Classic Grays",
    "Gonk Droid (GNK Power Droid) , Light Bluish Gray Body",
    "The Mandalorian / Din Djarin / 'Mando'",
    "Clone Trooper (Phase 1) - Black Head",
    "Imperial Stormtrooper - Detailed Armor",
    "Anakin Skywalker (Dark Brown Legs, Headset)",
    "Silver Protocol Droid (U-3PO)",
    "Luke Skywalker (Tatooine, White Legs, Stern / Smile Face Print)",
]


def _js(aufruf):
    """Die echten Funktionen aus app.js ausführen, nicht ihren Text lesen."""
    quelle = APP_JS.read_text()
    schnipsel = "\n".join(
        m.group(0) for name in ("jedipediaBegriff", "jedipediaSuchbegriff",
                                "jedipediaZiel")
        for m in [re.search(r"function %s\([^)]*\) \{.*?\n\}\n" % name,
                            quelle, re.S)] if m)
    konst = "\n".join(
        m.group(0) for m in re.finditer(
            r"^const JEDIPEDIA_[A-Z]+ =.*?;$", quelle, re.M | re.S))
    return subprocess.run(
        ["node", "-e", TABELLE.read_text() + konst + schnipsel
         + "\nconsole.log(JSON.stringify(%s));" % aufruf],
        capture_output=True, text=True, check=True).stdout


ohne_node = pytest.mark.skipif(not shutil.which("node"),
                               reason="node fehlt – die Proben lesen sonst nur Text")


def test_die_kennung_in_der_klammer_ueberlebt():
    """»Assassin Droid (IG-88)« wurde zu »Assassin Droid« – Trefferliste,
    obwohl »IG-88« ein Artikel ist. Die Klammer trug den Namen."""
    assert jt.begriff("Assassin Droid (IG-88) - Dark Bluish Gray") == "IG-88"
    assert jt.begriff("Silver Protocol Droid (U-3PO)") == "U-3PO"
    # Eine Beschreibung in Klammern bleibt draußen.
    assert jt.begriff("Ahsoka Tano (Padawan) - Tube Top") == "Ahsoka Tano"


def test_die_luecke_nach_der_klammer_verschwindet():
    """»Gonk Droid (GNK Power Droid) , Light …« hinterließ ein freistehendes
    Komma im Tabellenschlüssel."""
    assert jt.begriff("Gonk Droid (GNK Power Droid) , Light Bluish Gray") \
        == "Gonk Droid, Light Bluish Gray"


@ohne_node
def test_javascript_und_python_bilden_denselben_begriff():
    """Die Tabelle ist mit dem Python-Ergebnis beschriftet. Weichen die
    beiden Fassungen ab, findet die App ihre eigenen Einträge nicht mehr –
    und niemand sähe es, weil beide für sich richtig aussehen."""
    aus = json.loads(_js("[%s].map(jedipediaBegriff)"
                         % ",".join(json.dumps(n) for n in NAMEN)))
    assert aus == [jt.begriff(n) for n in NAMEN]


@ohne_node
def test_wer_in_der_tabelle_steht_kommt_im_artikel_an():
    """Der gemeldete Fehler: „Imperial Stormtrooper" führte auf die
    Suchseite. Jetzt steht in der Tabelle »Sturmtruppen«."""
    ziel = json.loads(_js('jedipediaZiel("Imperial Stormtrooper")'))
    assert "Spezial:Suche" not in ziel
    assert ziel.endswith("/wiki/Sturmtruppen")


@ohne_node
def test_wer_nicht_drinsteht_wird_weiter_gesucht():
    """Die Tabelle ersetzt die Suche nicht, sie geht ihr vor. Was fehlt,
    verhält sich wie vorher – kein toter Artikelpfad."""
    ziel = json.loads(_js('jedipediaZiel("Gibt Es Bestimmt Nicht Xyz")'))
    assert "Spezial:Suche?search=" in ziel


@ohne_node
def test_bei_mehreren_namen_wird_einer_gesucht():
    """»The Mandalorian / Din Djarin / 'Mando'« als Ganzes findet nichts."""
    assert jt.begriff(NAMEN[4]) == "The Mandalorian / Din Djarin / 'Mando'"
    ziel = json.loads(_js('jedipediaZiel("Irgendwer / Sonstwer / \'Wer\'")'))
    assert "Irgendwer" in ziel and "Sonstwer" not in ziel


def test_kein_eintrag_zeigt_auf_einen_sammelartikel():
    """**Der schädlichste Fehler beim Bauen der Tabelle.** Die
    Kandidatenkette nahm notfalls das letzte großgeschriebene Wort – bei
    »Battle Droid« also »Droid«, und das Wiki leitet es auf »Droide« um.
    Dreißig verschiedene Figuren zeigten auf denselben Sammelartikel. Ein
    falscher Artikel ist schlechter als eine Trefferliste."""
    inhalt = TABELLE.read_text()
    daten = json.loads("{" + inhalt.split("{", 1)[1].rsplit("}", 1)[0] + "}")
    assert daten, "die Tabelle ist leer"
    for sammel in ("Droide", "Leutnant", "Offizier", "Soldat"):
        treffer = [k for k, v in daten.items() if v == sammel]
        assert not treffer, "%s zeigen auf »%s«" % (treffer, sammel)


def test_gattungswoerter_kommen_aus_dem_bestand():
    """Was Gattung ist, wird gezählt, nicht geraten: Ein Wort, das viele
    verschiedene Figuren beendet, ist eine Kategorie."""
    g = jt.gattungswoerter(["Battle Droid", "Gonk Droid", "Assassin Droid",
                            "Clone Commando Wrecker"])
    assert "droid" in g
    assert "wrecker" not in g


def test_das_werkzeug_holt_nichts_im_betrieb():
    """Die App verlinkt nur. Kein Aufruf der Jedipedia darf im Frontend
    stehen – die Tabelle ist im Auslieferungsstand fertig."""
    quelle = APP_JS.read_text()
    for verboten in ("api.php", "fetch(\"https://www.jedipedia",
                     "fetch('https://www.jedipedia"):
        assert verboten not in quelle
