"""Das ↻ neben dem Bild holt frisch von BrickLink.

Zwei Fehler steckten darin. Erstens ging die Rebrickable-Nummer eines
bedruckten Teils unverändert hinaus – dieselbe Verwechslung wie beim Preis,
nur dass hier kein Bild statt keines Preises herauskam.

Zweitens ist `requests.HTTPError` eine **Unterklasse** von
`RequestException`. Ohne eigenen Zweig davor landete ein schlichtes 404 im
Ast „BrickLink nicht erreichbar" – gemeldet wurde also ein Ausfall, wo nur
die Nummer nicht passte.
"""
import time

import pytest
import requests

import core
import integrations
import main
from fastapi.testclient import TestClient

REB = "2586pr0028"
BL = "2586ps1"


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "b.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer, "
            "created_at) VALUES ('admin', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    return c


def http_fehler(code: int):
    antwort = requests.Response()
    antwort.status_code = code
    return requests.HTTPError(response=antwort)


def eintrag(nummer: str):
    return {"item_id": nummer, "item_type": "part", "name": "Schild",
            "img_url": f"https://img.bricklink.com/{nummer}.png"}


def katalog_nur_fuer(bekannt: str, protokoll: list):
    def hole(item_type, item_no):
        protokoll.append(item_no)
        if item_no != bekannt:
            raise http_fehler(404)
        return eintrag(item_no)
    return hole


# ------------------------------------------------------------ Die Zweitnummer

def test_bild_kommt_unter_der_bricklink_nummer(ctx, monkeypatch):
    gefragt = []
    monkeypatch.setattr(integrations, "bricklink_item",
                        katalog_nur_fuer(BL, gefragt))
    monkeypatch.setattr(main, "_bl_teil", lambda nr: (BL, eintrag(BL)))

    r = ctx.get(f"/api/lookup/part/{REB}")
    assert r.status_code == 200, r.text
    assert r.json()["img_url"].endswith(f"{BL}.png")
    assert gefragt[0] == REB, "erst die eigene Nummer"


def test_ohne_umweg_bleibt_es_beim_404(ctx, monkeypatch):
    monkeypatch.setattr(integrations, "bricklink_item",
                        katalog_nur_fuer("gibtsnicht", []))
    monkeypatch.setattr(main, "_bl_teil", lambda nr: (nr, None))

    r = ctx.get(f"/api/lookup/part/{REB}")
    assert r.status_code == 404, "kein Ausfall, sondern eine unbekannte Nummer"
    assert "fig-" not in r.json()["detail"]


def test_eine_bekannte_nummer_kostet_keinen_umweg(ctx, monkeypatch):
    """Der Umweg fragt Rebrickable – das darf nicht bei jedem Bild passieren."""
    monkeypatch.setattr(integrations, "bricklink_item",
                        katalog_nur_fuer(REB, []))
    umwege = []
    monkeypatch.setattr(main, "_bl_teil",
                        lambda nr: umwege.append(nr) or (nr, None))

    assert ctx.get(f"/api/lookup/part/{REB}").status_code == 200
    assert not umwege


# ------------------------------------------------------------ Ehrliche Codes

def test_ein_404_ist_kein_ausfall(ctx, monkeypatch):
    """Genau das ergab am Bildschirm „Fehler 502"."""
    def weg(item_type, item_no):
        raise http_fehler(404)

    monkeypatch.setattr(integrations, "bricklink_item", weg)
    monkeypatch.setattr(main, "_bl_teil", lambda nr: (nr, None))
    r = ctx.get("/api/lookup/minifig/sw0001")
    assert r.status_code == 404


def test_ein_echter_ausfall_bleibt_ein_ausfall(ctx, monkeypatch):
    def kaputt(item_type, item_no):
        raise http_fehler(500)

    monkeypatch.setattr(integrations, "bricklink_item", kaputt)
    r = ctx.get("/api/lookup/minifig/sw0001")
    assert r.status_code == 502 and "500" in r.json()["detail"]


def test_ein_zeitueberlauf_bleibt_ein_zeitueberlauf(ctx, monkeypatch):
    def lahm(item_type, item_no):
        raise requests.Timeout()

    monkeypatch.setattr(integrations, "bricklink_item", lahm)
    assert ctx.get("/api/lookup/minifig/sw0001").status_code == 504


def test_kein_netz_bleibt_kein_netz(ctx, monkeypatch):
    def kein_netz(item_type, item_no):
        raise requests.ConnectionError()

    monkeypatch.setattr(integrations, "bricklink_item", kein_netz)
    r = ctx.get("/api/lookup/minifig/sw0001")
    assert r.status_code == 502 and "erreichbar" in r.json()["detail"]


def test_figurenteile_melden_ein_404_als_404(ctx, monkeypatch):
    def weg(fig_no):
        raise http_fehler(404)

    monkeypatch.setattr(main, "_fig_parts_cached", weg)
    r = ctx.get("/api/fig_parts/sw0001")
    assert r.status_code == 404, "ein 404 ging bisher als Ausfall durch"


def test_der_text_passt_zum_bildabruf(ctx, monkeypatch):
    """Beim Preis fehlen **Verkäufe**, beim Bild fehlt der **Eintrag**.
    Die Preis-Fassung am Bild klang, als wäre nur gerade nichts verkauft
    worden – dabei kennt der Katalog die Nummer schlicht nicht."""
    def weg(item_type, item_no):
        raise http_fehler(404)

    monkeypatch.setattr(integrations, "bricklink_item", weg)
    monkeypatch.setattr(main, "_bl_teil", lambda nr: (nr, None))
    text = ctx.get("/api/lookup/part/9999xyz").json()["detail"]
    assert "kennt diese Nummer nicht" in text
    assert "verkauften Artikel" not in text
