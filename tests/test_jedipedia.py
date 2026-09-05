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
    `/wiki/Battle_Droid` wäre tot. Gesucht wird – und die Suche des Wikis
    springt von allein in den Artikel, wenn der Begriff der Titel ist."""
    quelle = APP_JS.read_text()
    assert "Spezial:Suche?search=" in quelle
    z = _fn("jedipediaZiel")
    assert "JEDIPEDIA_SUCHE" in z
    assert "/wiki/" not in z


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
    """»Clone Scout Trooper, 41st Elite Corps« findet nichts – die Einheit
    verhindert den Treffer, statt ihn zu schärfen."""
    assert jt.begriff("Clone Scout Trooper, 41st Elite Corps (Phase 2)") \
        == "Clone Scout Trooper"
    assert jt.begriff("Gonk Droid (GNK Power Droid) , Light Bluish Gray") \
        == "Gonk Droid"


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


def test_keine_bricklink_namen_im_ausgelieferten_stand():
    """**Der Fehler aus 2.77.0.** Dort lag eine Zuordnung im Frontend,
    deren Schlüssel BrickLink-Namen waren – in einem öffentlichen Repo.
    Namen sind BrickLinks Inhalt; `katalogdienst/veroeffentlichen.py`
    gibt aus demselben Grund nur Nummer und eigene Bildbeschreibung
    hinaus. Was hier ausgeliefert wird, darf keine Namensliste sein."""
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    assert not (frontend / "jedipedia-titel.js").exists()
    quelle = APP_JS.read_text()
    assert "JEDIPEDIA_TITEL" not in quelle


def test_das_werkzeug_schreibt_ueberhaupt_nichts():
    """Dasselbe eine Ebene tiefer: Das Nachschlage-Werkzeug darf sein
    Ergebnis gar nicht erst irgendwohin schreiben können, sonst passiert
    es wieder. Es misst – mehr nicht."""
    quelle = (Path(__file__).resolve().parents[1] / "tools"
              / "jedipedia_titel.py").read_text()
    assert not hasattr(jt, "schreiben")
    for schreibend in ("write_text(", "write_bytes(", '"w"', "'w'"):
        assert schreibend not in quelle, schreibend


def test_die_app_holt_nichts_von_jedipedia():
    """Sie verlinkt nur. Kein Aufruf des Wikis darf im Frontend stehen."""
    quelle = APP_JS.read_text()
    for verboten in ("api.php", 'fetch("https://www.jedipedia',
                     "fetch('https://www.jedipedia"):
        assert verboten not in quelle
