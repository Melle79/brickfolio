"""Bedruckte Teile heißen bei BrickLink anders.

Rebrickable nennt den Gungan-Schild `2586pr0028`, BrickLink `2586ps1`; den
Karbonitblock `87561pr0001` bzw. `87561pb01`. Fürs Thema wurde das seit jeher
übersetzt (`_bl_teil`), beim Preis nicht. Im Popup stand deshalb „BrickLink
kennt diese Nummer nicht – vermutlich eine Rebrickable-Nummer (fig-…)" –
falscher Grund, und der Rat dazu verwies auf ein Feld, das die Oberfläche bei
einem Teil überhaupt nicht anbietet.
"""
import time

import pytest
import requests

import core
import integrations
import main
from fastapi.testclient import TestClient

REB = "2586pr0028"          # so heißt der Gungan-Schild bei Rebrickable
BL = "2586ps1"              # und so bei BrickLink


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "z.db"))
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


def _teil(item_id=REB, item_type="part") -> int:
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, added_at) VALUES (?, ?, 'Schild', 1, 'new', ?)",
            (item_id, item_type, now))
        return cur.lastrowid


def nicht_gefunden():
    antwort = requests.Response()
    antwort.status_code = 404
    return requests.HTTPError(response=antwort)


def preis(nummer):
    return {"currency": "EUR", "min": 3, "avg": 6.5, "max": 9,
            "times_sold": 4, "condition": "N", "scope": "",
            "used_scope": "", "fell_back": False, "nr": nummer}


def guide_nur_fuer(bekannt: str, protokoll: list):
    """Attrappe: kennt genau eine Nummer, alles andere ist ein 404."""
    def guide(item_type, item_no, condition="U", scope=None, **kw):
        protokoll.append(item_no)
        if item_no != bekannt:
            raise nicht_gefunden()
        return preis(item_no)
    return guide


# ------------------------------------------------------------ Der Kern

def test_teil_bekommt_preis_unter_der_zweitnummer(ctx, monkeypatch):
    gefragt = []
    monkeypatch.setattr(integrations, "price_guide", guide_nur_fuer(BL, gefragt))
    monkeypatch.setattr(main, "_bl_teil", lambda nr: (BL, {"no": BL}))
    eintrag = _teil()

    r = ctx.get(f"/api/collection/{eintrag}/price?refresh=1")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["new"]["avg"] == 6.5
    assert body["bl_no"] == BL, "die benutzte Nummer muss dabeistehen"
    assert REB in gefragt and BL in gefragt, "erst die eigene, dann die andere"


def test_ohne_zweitnummer_bleibt_es_beim_fehler(ctx, monkeypatch):
    monkeypatch.setattr(integrations, "price_guide", guide_nur_fuer("gibtsnicht", []))
    monkeypatch.setattr(main, "_bl_teil", lambda nr: (nr, None))
    eintrag = _teil()

    r = ctx.get(f"/api/collection/{eintrag}/price?refresh=1")
    assert r.status_code == 404
    assert "fig-" not in r.json()["detail"], (
        "ein Teil ist keine Rebrickable-Figurennummer – der alte Text log "
        "und verwies auf ein Feld, das es hier nicht gibt")


def test_eine_figur_fragt_nicht_nach_einer_teilenummer(ctx, monkeypatch):
    """Der Umweg gilt nur für Teile; bei `fig-…` hilft er nicht und würde
    nur einen Abruf nach draußen kosten."""
    monkeypatch.setattr(integrations, "price_guide", guide_nur_fuer("nix", []))
    versuche = []
    monkeypatch.setattr(main, "_bl_teil",
                        lambda nr: versuche.append(nr) or (nr, None))
    eintrag = _teil("sw0001", "minifig")

    assert ctx.get(f"/api/collection/{eintrag}/price?refresh=1").status_code == 404
    assert not versuche


def test_ein_zeitueberlauf_ist_keine_unbekannte_nummer(ctx, monkeypatch):
    """Sonst gälte jede Störung als „kennt BrickLink nicht" – und der Eintrag
    bekäme am Ende noch den Vermerk, es gebe ihn nicht mehr."""
    def lahm(*a, **k):
        raise requests.Timeout()

    monkeypatch.setattr(integrations, "price_guide", lahm)
    eintrag = _teil()
    assert ctx.get(f"/api/collection/{eintrag}/price?refresh=1").status_code == 504


# ------------------------------------------------------------ Gemerkt wird

def test_die_zweitnummer_wird_nur_einmal_erfragt(ctx, monkeypatch):
    monkeypatch.setattr(integrations, "price_guide", guide_nur_fuer(BL, []))
    umwege = []
    monkeypatch.setattr(main, "_bl_teil",
                        lambda nr: umwege.append(nr) or (BL, {"no": BL}))
    eintrag = _teil()

    for _ in range(3):
        ctx.get(f"/api/collection/{eintrag}/price?refresh=1")
    assert umwege == [REB], f"jedes Mal nach draußen gefragt: {umwege}"


def test_auch_ein_leeres_ergebnis_wird_gemerkt(ctx, monkeypatch):
    """Sonst ginge dieselbe vergebliche Frage bei jedem Aufklappen erneut
    nach draußen – und die ist der langsame Teil."""
    monkeypatch.setattr(integrations, "price_guide", guide_nur_fuer("nix", []))
    umwege = []
    monkeypatch.setattr(main, "_bl_teil",
                        lambda nr: umwege.append(nr) or (nr, None))
    eintrag = _teil()

    for _ in range(3):
        ctx.get(f"/api/collection/{eintrag}/price?refresh=1")
    assert umwege == [REB]
    with core.db() as conn:
        row = conn.execute("SELECT bl_no FROM bl_nummern WHERE item_id = ?",
                           (REB,)).fetchone()
    assert row is not None and row["bl_no"] == ""


def test_ein_alter_fehlversuch_wird_wieder_geprueft(ctx, monkeypatch):
    """Ein Teil, das BrickLink heute nicht führt, kann morgen dort stehen."""
    with core.db() as conn:
        conn.execute("INSERT INTO bl_nummern (item_id, bl_no, checked_at) "
                     "VALUES (?, '', ?)",
                     (REB, int(time.time()) - main.BL_NUMMER_TTL - 1))
    monkeypatch.setattr(integrations, "price_guide", guide_nur_fuer(BL, []))
    monkeypatch.setattr(main, "_bl_teil", lambda nr: (BL, {"no": BL}))
    eintrag = _teil()

    r = ctx.get(f"/api/collection/{eintrag}/price?refresh=1")
    assert r.status_code == 200 and r.json()["bl_no"] == BL


# ------------------------------------------------------------ Der Endpunkt

def test_auch_der_direkte_abruf_nimmt_den_umweg(ctx, monkeypatch):
    """`/api/price/part/…` versorgt die Trefferliste beim Scannen."""
    monkeypatch.setattr(integrations, "price_guide", guide_nur_fuer(BL, []))
    monkeypatch.setattr(main, "_bl_teil", lambda nr: (BL, {"no": BL}))

    r = ctx.get(f"/api/price/part/{REB}")
    assert r.status_code == 200, r.text
    assert r.json()["bl_no"] == BL
