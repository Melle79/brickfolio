"""Favoriten und ausgeblendete Themen in der Katalogauswahl.

Bei 199 Themen ist die Auswahl ohne Vorsortierung unbrauchbar. Zwei Dinge
sind dabei leicht falsch gemacht:

- Ausblenden und Favorit dürfen nicht dasselbe Feld benutzen – wer ein
  Thema wieder einblendet, will seinen Stern wiederfinden.
- Die Auswahl darf nicht leer werden, ohne dass es jemand merkt.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _kat(conn, nr, name):
    conn.execute(
        "INSERT INTO katalog_index (item_no, item_type, name, such, img_url,"
        " category_id, jahr, updated_at)"
        " VALUES (?, 'minifig', ?, ?, '', '65', 2011, ?)",
        (nr, name, main._such_norm(name), int(time.time())))


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "tw.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('sven', 'x', 1, ?)", (now,)).lastrowid
        pid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('paul', 'x', 0, ?)", (now,)).lastrowid
        for i in range(1, 6):
            _kat(conn, "sw%04d" % i, "Star Wars %d" % i)
        for i in range(1, 4):
            _kat(conn, "cty%04d" % i, "Polizist %d" % i)
        _kat(conn, "fort001", "Battalion Brawler")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    p = TestClient(main.app)
    p.headers["Authorization"] = "Bearer " + core.create_token(pid, "paul", False)
    return {"sven": c, "paul": p, "uid": uid}


def _namen(client, alle=0):
    d = client.get("/api/katalog/liste/themen?alle=%d" % alle).json()
    return [t["thema"] for t in d["themen"]]


def test_ohne_wahl_ist_alles_da(ctx):
    assert set(_namen(ctx["sven"])) == {"Star Wars", "City", "Fortnite"}


def test_favorit_steht_oben(ctx):
    """Auch wenn das Thema klein ist – sonst bringt der Stern nichts."""
    assert _namen(ctx["sven"])[0] == "Star Wars"      # das größte
    ctx["sven"].post("/api/katalog/themen/wahl",
                     json={"thema": "Fortnite", "fav": True})
    assert _namen(ctx["sven"])[0] == "Fortnite"       # das kleinste


def test_ausgeblendetes_fehlt_in_der_auswahl(ctx):
    ctx["sven"].post("/api/katalog/themen/wahl",
                     json={"thema": "City", "sichtbar": False})
    assert "City" not in _namen(ctx["sven"])
    # In der Einstellungsliste steht es weiter – dort will man es ja
    # wieder einschalten können.
    assert "City" in _namen(ctx["sven"], alle=1)


def test_stern_ueberlebt_das_ausblenden(ctx):
    """Wer ein Thema wieder einblendet, findet seinen Stern wieder."""
    c = ctx["sven"]
    c.post("/api/katalog/themen/wahl", json={"thema": "City", "fav": True})
    c.post("/api/katalog/themen/wahl", json={"thema": "City", "sichtbar": False})
    c.post("/api/katalog/themen/wahl", json={"thema": "City", "sichtbar": True})
    nach = {t["thema"]: t for t in
            c.get("/api/katalog/liste/themen").json()["themen"]}
    assert nach["City"]["fav"] is True


def test_die_wahl_gehoert_dem_benutzer(ctx):
    """Pauls Auswahl darf Svens nicht anfassen."""
    ctx["sven"].post("/api/katalog/themen/wahl",
                     json={"thema": "City", "sichtbar": False})
    assert "City" not in _namen(ctx["sven"])
    assert "City" in _namen(ctx["paul"])


def test_nur_favoriten_raeumt_den_rest_weg(ctx):
    c = ctx["sven"]
    c.post("/api/katalog/themen/wahl", json={"thema": "Fortnite", "fav": True})
    d = c.post("/api/katalog/themen/wahl/alle",
               json={"was": "nur_favoriten"}).json()
    assert d["ok"] is True
    assert _namen(c) == ["Fortnite"]
    assert d["versteckt"] == 2 and d["gesamt"] == 3


def test_alle_ein_holt_alles_zurueck(ctx):
    c = ctx["sven"]
    c.post("/api/katalog/themen/wahl/alle", json={"was": "alle_aus"})
    assert _namen(c) == []
    c.post("/api/katalog/themen/wahl/alle", json={"was": "alle_ein"})
    assert len(_namen(c)) == 3


def test_die_einstellungsliste_ist_alphabetisch(ctx):
    """Dort sucht man einen Namen – aus einer Größenfolge springt er nicht
    ins Auge."""
    namen = _namen(ctx["sven"], alle=1)
    assert namen == sorted(namen, key=str.lower)


def test_kaputte_gespeicherte_wahl_wirft_nicht(ctx):
    core.set_user_setting(ctx["uid"], main.KATALOG_THEMEN_WAHL, "kein json")
    assert set(_namen(ctx["sven"])) == {"Star Wars", "City", "Fortnite"}


def test_schnelle_tipper_gehen_nicht_verloren(ctx):
    """Lesen, ändern, schreiben muss am Stück laufen.

    Die ganze Wahl steht als **eine** JSON-Zeile. Wer in der Liste zügig
    mehrere Themen antippt, schickt Anfragen, die sich überholen: Jede
    liest denselben alten Stand und schreibt ihr eigenes Thema zurück –
    die übrigen Änderungen sind danach weg. Gemessen am 29.08.2026 kam von
    fünf Tippern einer an.
    """
    import threading

    c = ctx["sven"]
    themen = ["Star Wars", "City", "Fortnite"]
    fehler = []

    def tippen(t):
        try:
            c.post("/api/katalog/themen/wahl", json={"thema": t, "fav": True})
        except Exception as e:      # pragma: no cover - nur zur Diagnose
            fehler.append(e)

    faeden = [threading.Thread(target=tippen, args=(t,)) for t in themen
              for _ in range(4)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join()

    assert not fehler
    nach = {t["thema"]: t for t in
            c.get("/api/katalog/liste/themen").json()["themen"]}
    verloren = [t for t in themen if not nach[t]["fav"]]
    assert not verloren, "verlorene Markierungen: %s" % verloren
