"""Der Steckbrief und der Foto-Knopf.

Zwei Wünsche aus dem Betrieb, die dieselbe Wurzel haben: Überall, wo eine
Figur nur als *Zeile* auftaucht – im Set, in der Teileliste, unter den
fehlenden Set-Figuren, auf den Listen –, fehlte die Antwort auf die Frage,
die man dort hat: was ist das, habe ich es schon, was ist es wert? Ein Tipp
auf die Zeile öffnet jetzt den Steckbrief.

Und: „📷 Nur Foto dazu" hängt ein Foto an einen Artikel, den es schon gibt.
Ohne Artikel gibt es nichts, woran es hängen könnte – der Knopf stand aber
immer da. Die Wunschliste zählt dabei bewusst nicht: Was man sich wünscht,
hat man gerade nicht.

Der Steckbrief lebt im Browser. Prüfbar ist hier, dass er überall verdrahtet
ist und aus welcher Quelle er sich speist – die Sichtprüfung lief auf einer
laufenden Instanz.
"""
import re
import time
from pathlib import Path

import pytest

import core
import main
from fastapi.testclient import TestClient

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def html() -> str:
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "s.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)",
            (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


# ------------------------------------------------------------- Das Popup gibt es

def test_das_popup_steht_im_html():
    h = html()
    for teil in ('id="figinfo-overlay"', 'id="figinfo-body"',
                 'id="btn-figinfo-close"'):
        assert teil in h, f"{teil} fehlt"


def test_es_schliesst_auf_drei_wegen():
    j = js()
    assert 'btn-figinfo-close").addEventListener' in j, "kein Kreuz"
    assert re.search(r'figinfo-overlay"\)\.addEventListener\("click"', j), \
        "Tippen daneben schließt nicht"
    assert "steckbriefSchliessen" in j and "Escape" in j, "Escape fehlt"


def test_die_galerie_liegt_ueber_dem_steckbrief():
    """Tippt man im Steckbrief aufs Bild, muss die Galerie **davor**
    erscheinen und nicht dahinter verschwinden."""
    c = css()
    overlay = re.search(r"\.help-overlay\s*\{[^}]*z-index:\s*(\d+)", c)
    lightbox = re.search(r"\.lightbox\s*\{[^}]*z-index:\s*(\d+)", c)
    assert overlay and lightbox, "z-index nicht gefunden"
    assert int(lightbox.group(1)) > int(overlay.group(1)), (
        f"Galerie ({lightbox.group(1)}) liegt nicht über dem Steckbrief "
        f"({overlay.group(1)})")


# --------------------------------------------------------- Überall verdrahtet

def test_alle_figurenzeilen_tragen_den_marker():
    """Genau der Fehler von 2.11.0: Ein Test, der eine Klasse wörtlich sucht,
    übersieht die Zeilen mit weiteren Klassen. Deshalb hier über die Zahl."""
    j = js()
    zeilen = len(re.findall(r'<div class="fig-row[^"]*"', j))
    mit_marker = len(re.findall(r'<div class="fig-row[^"]*"[^>]*data-info=', j))
    # Die beiden Auswahl-Dialoge (Figuren zum Set übernehmen / mit löschen)
    # sind Ankreuzlisten – dort führt ein Tipp die Auswahl aus, nicht den
    # Steckbrief.
    assert zeilen - mit_marker <= 2, (
        f"{zeilen - mit_marker} Figurenzeilen ohne Steckbrief-Marker")
    assert mit_marker >= 5, f"nur {mit_marker} Zeilen verdrahtet"


def test_die_wunschliste_ist_auch_verdrahtet():
    assert re.search(r'<div class="card-title tappbar"[^>]*data-info=', js()), \
        "auf der Wunschliste öffnet nichts"


def test_der_marker_traegt_typ_und_nummer():
    """`3001` ist Set *und* Stein – ohne Typ zeigt der Steckbrief das Falsche."""
    for treffer in re.findall(r'data-info="([^"]*)"', js()):
        assert "|" in treffer, f"Marker ohne Typ: {treffer}"


def test_knoepfe_und_bild_behalten_ihre_aufgabe():
    j = js()
    stelle = j[j.index("[data-info]"):][:900]
    assert "button, a, input, select, label, .card-img" in stelle, (
        "ein Tipp auf einen Knopf oder das Bild würde den Steckbrief öffnen")


# ------------------------------------------------- Eine Farbe pro Bedeutung

def test_einkaufsliste_und_wunschliste_sehen_verschieden_aus():
    """Vorher waren beide gelb. „Liegt im Korb" und „fehlt euch" ist aber das
    Gegenteil voneinander – gleiche Farbe hieße dann gar nichts."""
    c = css()
    liste = re.search(r"\.badge-list\s*\{([^}]*)\}", c)
    wunsch = re.search(r"\.badge-wanted\s*\{([^}]*)\}", c)
    assert liste and wunsch
    assert "--blue" in liste.group(1), "die Listen-Marke ist nicht blau"
    assert "--yellow" in wunsch.group(1), "die Wunsch-Marke ist nicht gelb"


def test_es_gibt_nur_eine_klasse_fuer_die_einkaufsliste():
    assert "badge-onlist" not in js() and "badge-onlist" not in css(), (
        "zwei Klassen für dieselbe Aussage")


# --------------------------------------------------- „Nur Foto dazu"

def test_der_fotoknopf_startet_verborgen():
    assert re.search(r'data-foto="\$\{i\}" hidden', js()), (
        "der Knopf steht sofort da, auch ohne Artikel")


def test_der_fotoknopf_kommt_bei_besitz_und_liste_aber_nicht_bei_wunsch():
    j = js()
    stelle = j[j.index("const vorhanden ="):][:400]
    assert "d.owned > 0" in stelle, "die Sammlung zählt nicht"
    assert "d.on_lists" in stelle, "die Einkaufsliste zählt nicht"
    assert "wanted" not in stelle, (
        "die Wunschliste zählt mit – was man sich wünscht, hat man nicht")


# ------------------------------------------------------------ Die Quelle stimmt

def test_die_quelle_liefert_alles_was_der_steckbrief_zeigt(ctx):
    """Der Steckbrief holt alles aus einem Aufruf. Bleibt ein Feld weg,
    fehlt im Popup eine Zeile, ohne dass es jemand merkt."""
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " price_new, price_used, price_updated_at, added_at) VALUES "
            "('sw0815', 'minifig', 'Rebel Pilot', 2, 9.0, 6.0, ?, ?)",
            (now, now))
        lid = conn.execute("INSERT INTO shopping_lists (name, created_at) "
                           "VALUES ('Flohmarkt', ?)", (now,)).lastrowid
        conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name,"
            " qty, added_at) VALUES (?, 'sw0815', 'minifig', 'x', 1, ?)",
            (lid, now))
    r = ctx.post("/api/suggest_info?detail=1",
                 json={"items": [{"item_id": "sw0815", "item_type": "minifig"}]})
    assert r.status_code == 200
    d = r.json()["sw0815"]
    assert d["owned"] == 2
    assert d["on_lists"] == ["Flohmarkt"]
    assert d["new"] == 9.0 and d["used"] == 6.0


def test_unbekannte_nummer_liefert_einen_leeren_steckbrief(ctx):
    """Nicht erfasst ist eine Antwort, kein Fehler – das Popup zeigt dann
    „noch nirgends erfasst"."""
    r = ctx.post("/api/suggest_info?detail=1",
                 json={"items": [{"item_id": "sw9999", "item_type": "minifig"}]})
    assert r.status_code == 200
    d = r.json()["sw9999"]
    assert d["owned"] == 0
    assert not d.get("wanted")
    assert not d.get("on_lists")
