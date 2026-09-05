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
    kopf, rest = z.split("if (titel)", 1)
    assert "JEDIPEDIA_ARTIKEL" not in kopf
    assert "JEDIPEDIA_ARTIKEL + encodeURIComponent(titel" in rest
    assert "JEDIPEDIA_SUCHE" in rest


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


# ── Der Begriff soll selbst der Artikeltitel sein ─────────────────────
#
# Am 05.09.2026 gemeldet: „Bei vielen kommt nur die Suchseite raus." Die
# Suche des Wikis springt von allein in den Artikel, sobald der Begriff
# der Titel ist – sie tat es nur selten, weil BrickLinks Namen Beiwerk
# mitschleppen. Nachgemessen an 563 Star-Wars-Figuren: 151 vorher, 218
# nachher, ohne dass eine Zeile Wiki-Inhalt mitgeliefert würde.

import json
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import jedipedia_titel as jt                                    # noqa: E402

TABELLE = (Path(__file__).resolve().parents[1] / "frontend"
           / "jedipedia-titel.js")

NAMEN = [
    "Assassin Droid (IG-88) - Dark Bluish Gray, Printed Head",
    "Astromech Droid, C1-10P (Chopper) - White Body",
    "Astromech Droid, R2-D2, Light Bluish Gray Head",
    "Boba Fett - Classic Grays",
    "Gonk Droid (GNK Power Droid) , Light Bluish Gray Body",
    "The Mandalorian / Din Djarin / 'Mando'",
    "Clone Scout Trooper, 41st Elite Corps (Phase 2) - Kama",
    "Ahsoka Tano (Padawan) - Tube Top and Belt",
    "Silver Protocol Droid (U-3PO)",
    "Luke Skywalker (Tatooine, White Legs, Stern / Smile Face Print)",
]

ohne_node = pytest.mark.skipif(
    not shutil.which("node"),
    reason="node fehlt – die Probe läse sonst nur Text")


def _js(aufruf):
    """Die echten Funktionen aus app.js ausführen, nicht ihren Text lesen."""
    quelle = APP_JS.read_text()
    stuecke = [m.group(0) for m in re.finditer(
        r"^const JEDIPEDIA_[A-Z]+ =.*?;$", quelle, re.M | re.S)]
    for name in ("jedipediaBegriff", "jedipediaSuchbegriff", "jedipediaZiel"):
        m = re.search(r"function %s\([^)]*\) \{.*?\n\}\n" % name,
                      quelle, re.S)
        assert m, name
        stuecke.append(m.group(0))
    return subprocess.run(
        ["node", "-e", "\n".join(stuecke)
         + "\nconsole.log(JSON.stringify(%s));" % aufruf],
        capture_output=True, text=True, check=True).stdout


def test_die_kennung_gewinnt_wo_sie_steht():
    """»Assassin Droid (IG-88)« wurde zu »Assassin Droid« – Trefferliste,
    obwohl »IG-88« im Wiki der Artikeltitel ist. Dasselbe hinter dem
    Komma: »Astromech Droid, C1-10P« verschenkte »C1-10P«."""
    assert jt.begriff("Assassin Droid (IG-88) - Dark Bluish Gray") == "IG-88"
    assert jt.begriff("Astromech Droid, C1-10P (Chopper)") == "C1-10P"
    assert jt.begriff("Silver Protocol Droid (U-3PO)") == "U-3PO"
    assert jt.begriff("Astromech Droid, R2-D2, Light Gray Head") == "R2-D2"
    # Eine Beschreibung in Klammern bleibt draußen.
    assert jt.begriff("Ahsoka Tano (Padawan) - Tube Top") == "Ahsoka Tano"


def test_hinter_dem_komma_steht_beiwerk():
    """Die entfernte Klammer ließ ein freistehendes Komma zurück, und die
    Bemalung dahinter findet im Wiki nichts – sie verhindert den Treffer,
    statt ihn zu schärfen. Die **Einheit** ist der Gegenfall und bleibt
    stehen; das prüft `test_die_einheit_bleibt_stehen_die_bemalung_nicht`."""
    assert jt.begriff("Gonk Droid (GNK Power Droid) , Light Bluish Gray") \
        == "Gonk Droid"
    assert jt.begriff("Boba Fett, Young") == "Boba Fett"


@ohne_node
def test_javascript_und_python_bilden_denselben_begriff():
    """Das Werkzeug misst, wie gut die Begriffe treffen – die App bildet
    sie. Weichen die beiden ab, misst das Werkzeug etwas anderes, als der
    Anwender bekommt, und beide sähen für sich richtig aus."""
    aus = json.loads(_js("[%s].map(jedipediaBegriff)"
                         % ",".join(json.dumps(n) for n in NAMEN)))
    assert aus == [jt.begriff(n) for n in NAMEN]


@ohne_node
def test_bei_mehreren_namen_wird_einer_gesucht():
    """»The Mandalorian / Din Djarin / 'Mando'« als Ganzes findet nichts."""
    ziel = json.loads(_js("jedipediaZiel(\"Irgendwer / Sonstwer\")"))
    assert "Irgendwer" in ziel and "Sonstwer" not in ziel


def test_kein_schluessel_traegt_eine_bricklink_beschreibung():
    """**Die Grenze aus 2.77.0, diesmal als Probe.** Damals standen ganze
    Katalognamen in der Tabelle – »Astromech Droid, R2-D2, Light Bluish
    Gray Head«. Namen sind Star-Wars-Begriffe und dürfen mit; BrickLinks
    Beschreibung im Titel nicht.

    Geprüft wird nicht gegen eine Wortliste – die kennte nie jede Bemalung
    –, sondern über die Regel selbst: `jedipediaBegriff` löst die
    Beschreibung heraus, also **muss jeder Schlüssel schon sein eigenes
    Ergebnis sein**. Steckt eine Beschreibung darin, ändert die Regel ihn,
    und die Probe fällt durch."""
    daten = json.loads("{" + TABELLE.read_text().split("{", 1)[1]
                       .rsplit("}", 1)[0] + "}")
    assert daten, "die Tabelle ist leer"
    schmutzig = [k for k in daten if jt.begriff(k) != k]
    assert not schmutzig, schmutzig


def test_die_einheit_bleibt_stehen_die_bemalung_nicht():
    """Sven am 05.09.2026: Bei »Clone Trooper Commander, 187th Legion« ist
    die 187. Legion der interessantere Verweis. Die Farbe des Kopfes ist
    es nicht."""
    assert jt.begriff("Clone Trooper Commander, 187th Legion (Phase 2)"
                      " - Nougat Head") == "Clone Trooper Commander, 187th Legion"
    assert jt.begriff("Snowtrooper, Printed Legs, Dark Tan Hands, Frown") \
        == "Snowtrooper"


def test_bei_einem_namen_geht_die_person_vor_der_einheit():
    """Svens zweiter Hinweis: »Commander Fox« gibt es, also gehört der
    Verweis zu ihm – nicht zu seiner Garde. Bei einer bloßen Rolle ist es
    umgekehrt, sonst landete jeder Klonkommandant auf derselben Seite."""
    daten = json.loads("{" + TABELLE.read_text().split("{", 1)[1]
                       .rsplit("}", 1)[0] + "}")
    assert daten.get("Clone Trooper Commander Fox, Coruscant Guard") \
        == "Commander Fox"
    assert daten.get("Clone Trooper Commander, 187th Legion") == "187. Legion"


def test_keine_begriffsklaerung_in_der_tabelle():
    """»Cody«, »Fox«, »Hammer« – lauter Klonkrieger, und jeder dieser
    Titel ist im Wiki eine Begriffsklärungsseite. Wer darauf klickt, steht
    vor einer Auswahlliste statt vor der Figur. Die bekannten Fälle dürfen
    nicht als Ziel auftauchen."""
    daten = json.loads("{" + TABELLE.read_text().split("{", 1)[1]
                       .rsplit("}", 1)[0] + "}")
    for seite in ("Cody", "Fox", "Gree", "Bly", "Hammer", "Hunter", "Jag",
                  "Rex", "Bacara", "Gregor", "Echo", "Kommandodroide",
                  "Mausdroide", "Schneetruppen", "Sith-Soldaten",
                  "Stoßtruppen", "Droide"):
        treffer = [k for k, v in daten.items() if v == seite]
        assert not treffer, "%s zeigen auf »%s«" % (treffer, seite)


def test_das_werkzeug_schreibt_nur_die_eine_datei():
    """Es darf die Tabelle schreiben – aber nur sie. Ein zweites Ziel wäre
    der Weg, auf dem versehentlich wieder Katalogtext hinausginge."""
    quelle = (Path(__file__).resolve().parents[1] / "tools"
              / "jedipedia_titel.py").read_text()
    assert quelle.count("write_text(") == 1
    assert 'ZIEL = Path(__file__).resolve().parents[1] / "frontend"' in quelle


def test_die_app_holt_nichts_von_jedipedia():
    """Sie verlinkt nur. Kein Aufruf des Wikis darf im Frontend stehen."""
    quelle = APP_JS.read_text()
    for verboten in ("api.php", 'fetch("https://www.jedipedia',
                     "fetch('https://www.jedipedia"):
        assert verboten not in quelle
