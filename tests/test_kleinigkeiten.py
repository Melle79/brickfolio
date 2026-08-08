"""Vier Funde aus dem vollständigen Funktionstest.

Keiner davon hat je jemanden umgebracht – deshalb lagen sie liegen. Gemeinsam
ist ihnen, dass sie **still** danebengehen: Der Benutzername wird angelegt und
ist unbrauchbar, der Einrichter sieht die halbe App nicht, gelöschte Artikel
lassen Dateien zurück, die niemand mehr sehen kann, und in der Galerie steht
ein Bild, das es nicht gibt.
"""
import os
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def frisch(tmp_path, monkeypatch):
    """Leere Instanz – noch ohne Benutzer, für die Einrichtung."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "k.db"))
    core.init_db()
    return TestClient(main.app)


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "k.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)",
            (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


# ------------------------------------------------------- 1. Benutzername

def test_nur_leerzeichen_kommt_nicht_durch(ctx):
    """Die Längenprüfung zählt die **rohe** Eingabe, gestrippt wurde erst
    danach: „  " kam als zwei Zeichen durch und landete als leerer Name in
    der Datenbank. Anmelden konnte sich damit niemand mehr."""
    r = ctx.post("/api/users", json={"username": "   ", "password": "geheim12"})
    assert r.status_code == 400
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 1


def test_steuerzeichen_kommen_nicht_durch(ctx):
    """Ein Name mit Zeilenumbruch zerlegt jede Liste, in der er auftaucht."""
    r = ctx.post("/api/users", json={"username": "Sv\nen", "password": "geheim12"})
    assert r.status_code == 400


def test_umgebende_leerzeichen_werden_abgeschnitten(ctx):
    ctx.post("/api/users", json={"username": "  Finn  ", "password": "geheim12"})
    with core.db() as conn:
        namen = [r[0] for r in conn.execute("SELECT username FROM users")]
    assert "Finn" in namen, namen


def test_gleicher_name_in_anderer_schreibweise_wird_abgewiesen(ctx):
    assert ctx.post("/api/users",
                    json={"username": "Finn", "password": "geheim12"}
                    ).status_code == 200
    r = ctx.post("/api/users", json={"username": "finn", "password": "geheim12"})
    assert r.status_code == 409


def test_auch_das_umbenennen_prueft(ctx):
    r = ctx.post("/api/me/username", json={"username": "  "})
    assert r.status_code == 400


def test_auch_die_einrichtung_prueft(frisch):
    r = frisch.post("/api/setup", json={"username": " \t ", "password": "geheim12"})
    assert r.status_code == 400


# --------------------------------------------------- 2. Der erste Admin

def test_wer_einrichtet_ist_auch_profi(frisch):
    """Vorher blieb er Standard-Benutzer: Kaufpreise, Einkaufslisten und
    Verkaufsliste waren ausgeblendet, und freischalten musste er sich in der
    Benutzerverwaltung selbst."""
    r = frisch.post("/api/setup", json={"username": "Sven", "password": "geheim12"})
    assert r.status_code == 200
    assert r.json()["is_dealer"] is True
    with core.db() as conn:
        assert conn.execute("SELECT is_dealer FROM users").fetchone()[0] == 1


def test_der_zweite_benutzer_ist_es_nicht_automatisch(frisch):
    """Die Profi-Rolle gehört dem Eigner, nicht jedem."""
    frisch.post("/api/setup", json={"username": "Sven", "password": "geheim12"})
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " created_at) VALUES ('Finn', 'x', 0, ?)",
                     (int(time.time()),))
        assert conn.execute(
            "SELECT COALESCE(is_dealer, 0) FROM users WHERE username = 'Finn'"
        ).fetchone()[0] == 0


# ------------------------------------------------------------ 3. Fotos

def foto_anlegen(item_type="minifig", item_id="sw0815") -> str:
    """Legt eine Datei im Upload-Ordner an und hängt sie an einen Artikel."""
    name = "0123456789abcdef0123456789abcde0.jpg"
    pfad = os.path.join(main._uploads_dir(), name)
    with open(pfad, "wb") as f:
        f.write(b"jpeg")
    url = "/uploads/" + name
    with core.db() as conn:
        conn.execute(
            "INSERT INTO item_photos (item_type, item_id, url, added_at)"
            " VALUES (?, ?, ?, ?)", (item_type, item_id, url, int(time.time())))
    return pfad


def in_sammlung(item_id="sw0815", item_type="minifig", zustand="used") -> int:
    with core.db() as conn:
        return conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity,"
            " condition, added_at) VALUES (?, ?, 'Rebel Pilot', 1, ?, ?)",
            (item_id, item_type, zustand, int(time.time()))).lastrowid


def test_letzte_zeile_geloescht_raeumt_die_fotos_weg(ctx):
    eintrag = in_sammlung()
    pfad = foto_anlegen()
    r = ctx.delete(f"/api/collection/{eintrag}")
    assert r.status_code == 200
    assert r.json()["photos_removed"] == 1
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM item_photos"
                            ).fetchone()["c"] == 0
    assert not os.path.exists(pfad), "die Datei liegt weiter auf der Platte"


def test_zweite_zeile_desselben_artikels_haelt_die_fotos(ctx):
    """Das Foto hängt am Artikel, nicht an der Zeile: Dieselbe Figur kann ein
    zweites Mal in der Sammlung stehen, in anderem Zustand."""
    erste = in_sammlung(zustand="used")
    in_sammlung(zustand="new")
    pfad = foto_anlegen()
    r = ctx.delete(f"/api/collection/{erste}")
    assert r.json()["photos_removed"] == 0
    assert os.path.exists(pfad)


def test_ein_wunsch_haelt_die_fotos(ctx):
    eintrag = in_sammlung()
    pfad = foto_anlegen()
    with core.db() as conn:
        conn.execute("INSERT INTO wanted (item_id, item_type, name, added_at)"
                     " VALUES ('sw0815', 'minifig', 'Rebel Pilot', ?)",
                     (int(time.time()),))
    ctx.delete(f"/api/collection/{eintrag}")
    assert os.path.exists(pfad), "der Wunsch braucht das Foto noch"


def test_eine_geteilte_datei_bleibt_liegen(ctx):
    """Dieselbe Aufnahme kann an mehreren Artikeln hängen. Wer das übersieht,
    reißt dem anderen das Bild weg."""
    eintrag = in_sammlung()
    pfad = foto_anlegen()
    with core.db() as conn:
        conn.execute(
            "INSERT INTO item_photos (item_type, item_id, url, added_at)"
            " VALUES ('minifig', 'sw9999', '/uploads/"
            "0123456789abcdef0123456789abcde0.jpg', ?)", (int(time.time()),))
    ctx.delete(f"/api/collection/{eintrag}")
    assert os.path.exists(pfad), "dem anderen Artikel wurde das Bild entzogen"


def test_ein_einzeln_geloestes_foto_nimmt_die_datei_mit(ctx):
    in_sammlung()
    pfad = foto_anlegen()
    with core.db() as conn:
        pid = conn.execute("SELECT id FROM item_photos").fetchone()[0]
    r = ctx.delete(f"/api/item_photos/{pid}")
    assert r.json()["file_removed"] is True
    assert not os.path.exists(pfad)


def test_fremde_adressen_werden_nicht_angefasst():
    """Nur eigene Uploads – ein Katalogbild von BrickLink gehört uns nicht."""
    assert main._datei_wegwerfen(
        "https://img.bricklink.com/ItemImage/MN/0/sw0815.png") is False


# ------------------------------------------------- 4. Geratene Bildadresse

def ohne_schluessel(monkeypatch):
    monkeypatch.setattr(main.integrations, "bricklink_enabled", lambda: False)
    monkeypatch.setattr(main.integrations, "rebrickable_enabled", lambda: False)


def antwortet_mit(monkeypatch, code, zaehler=None):
    class Antwort:
        status_code = code

    def head(*a, **k):
        if zaehler is not None:
            zaehler.append(1)
        return Antwort()

    monkeypatch.setattr(main.requests, "head", head)
    main._BILD_DA_CACHE.clear()


def test_ein_klares_gibt_es_nicht_wirft_die_adresse_raus(ctx, monkeypatch):
    """Die ItemImage-Adresse wird aus Typ und Nummer zusammengebaut. Stimmt
    sie nicht, stand ein leerer Rahmen in der Galerie."""
    ohne_schluessel(monkeypatch)
    antwortet_mit(monkeypatch, 404)
    r = ctx.get("/api/images/minifig/sw0815")
    assert r.status_code == 200
    assert r.json()["images"] == [], r.json()


def test_ein_vorhandenes_bild_bleibt_drin(ctx, monkeypatch):
    ohne_schluessel(monkeypatch)
    antwortet_mit(monkeypatch, 200)
    bilder = ctx.get("/api/images/minifig/sw0815").json()["images"]
    assert bilder == ["https://img.bricklink.com/ItemImage/MN/0/sw0815.png"]


def test_ohne_netz_bleibt_die_vermutung_stehen(ctx, monkeypatch):
    """Der wichtigere Fall: Die Beweislast liegt beim Weglassen. Wer bei
    jedem Netzhänger die Adresse verwirft, liefert eine leere Galerie – und
    das ist schlimmer als ein Bild, das vielleicht lädt."""
    ohne_schluessel(monkeypatch)
    main._BILD_DA_CACHE.clear()

    def kaputt(*a, **k):
        raise main.requests.ConnectionError("kein Netz")

    monkeypatch.setattr(main.requests, "head", kaputt)
    bilder = ctx.get("/api/images/minifig/sw0815").json()["images"]
    assert bilder == ["https://img.bricklink.com/ItemImage/MN/0/sw0815.png"]


def test_auch_ein_seltsamer_statuscode_wirft_nichts_weg(ctx, monkeypatch):
    """403 oder 500 heißen nicht „gibt es nicht", sondern „frag später"."""
    ohne_schluessel(monkeypatch)
    antwortet_mit(monkeypatch, 403)
    bilder = ctx.get("/api/images/minifig/sw0815").json()["images"]
    assert bilder == ["https://img.bricklink.com/ItemImage/MN/0/sw0815.png"]


def test_das_ergebnis_wird_gemerkt(monkeypatch):
    """Sonst fragt jede geöffnete Galerie erneut beim CDN nach."""
    rufe = []
    antwortet_mit(monkeypatch, 404, rufe)
    url = "https://img.bricklink.com/ItemImage/MN/0/sw4242.png"
    assert main._bild_fehlt_sicher(url) is True
    assert main._bild_fehlt_sicher(url) is True
    assert len(rufe) == 1, f"{len(rufe)} Abrufe statt einem"


def test_ein_netzfehler_wird_nicht_gemerkt(monkeypatch):
    """Ein Aussetzer darf sich nicht festsetzen – gleich kann es wieder gehen."""
    main._BILD_DA_CACHE.clear()

    def kaputt(*a, **k):
        raise main.requests.Timeout("zu langsam")

    monkeypatch.setattr(main.requests, "head", kaputt)
    url = "https://img.bricklink.com/ItemImage/MN/0/sw4243.png"
    assert main._bild_fehlt_sicher(url) is False
    assert url not in main._BILD_DA_CACHE


def test_ein_fehlendes_bild_wird_kuerzer_gemerkt_als_ein_vorhandenes():
    assert main.BILD_DA_TTL_NEIN < main.BILD_DA_TTL_JA
    assert main.BILD_DA_TTL_NEIN <= 15 * 60
