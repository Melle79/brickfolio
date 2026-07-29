"""Katalogbilder auf der eigenen Instanz.

Der Zweck ist Datensparsamkeit: Nach dem einmaligen Holen fragt kein Browser
mehr bei BrickLink, Rebrickable oder Brickognize an. Damit steht und fällt
alles an zwei Punkten – der Abruf darf **nur** zu den festen Katalog-Hosts
gehen, und der Dateiname darf sich nicht aus einer Teilenummer ausrechnen
lassen. Sonst hätte man einen Weg nach außen bzw. verriete doch, was hier
steht.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient

BILD = "https://img.bricklink.com/ItemImage/MN/0/sw0001a.png"


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "img.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


def _eintrag(img_url, item_id="sw0001a"):
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, img_url, "
            "quantity, condition, added_at) VALUES (?, 'minifig', ?, ?, 1, "
            "'used', ?)", (item_id, item_id, img_url, now))


# ------------------------------------------------------ Nur feste Hosts

@pytest.mark.parametrize("url", [
    "https://beispiel.test/bild.png",
    "http://127.0.0.1:8080/geheim.png",
    "https://img.bricklink.com.angreifer.test/x.png",
    "file:///etc/passwd",
    "https://169.254.169.254/latest/meta-data/",
])
def test_fremde_adressen_werden_abgelehnt(ctx, url):
    """Der Abruf läuft auf dem Server. Ein offener Weg dorthin wäre ein
    Werkzeug, um von innen beliebige Adressen anzufragen."""
    assert main._katalog_bild(url) is None
    assert ctx.get("/catalog", params={"u": url}).status_code == 404


def test_katalog_hosts_sind_erlaubt():
    for host in ("img.bricklink.com", "cdn.rebrickable.com",
                 "storage.googleapis.com"):
        assert host in integrations.BILD_HOSTS


def test_prufung_gilt_auch_fuer_den_alten_aufrufer():
    """`fetch_catalog_image` ohne Liste bleibt bei der engeren Auswahl –
    die Nummern-Auflösung soll nicht nebenbei mehr dürfen."""
    with pytest.raises(ValueError):
        integrations.fetch_catalog_image(
            "https://storage.googleapis.com/x/y.webp")


# ------------------------------------------------------ Dateiname

def test_gleiche_figur_ein_name():
    """BrickLink liefert dasselbe Motiv über mehrere Endpunkte – daraus darf
    nicht dreimal dieselbe Datei werden."""
    a = main._katalog_name("https://img.bricklink.com/ItemImage/MN/0/sw0001a.png")
    b = main._katalog_name("//img.bricklink.com/ML/sw0001a.jpg")
    assert a == b and a.endswith(".jpg")


def test_name_ist_ohne_schluessel_nicht_ausrechenbar(monkeypatch):
    """Sonst könnte jemand aus einer Teilenummer den Dateinamen bilden und so
    erfahren, was in dieser Sammlung steht."""
    vorher = main._katalog_name(BILD)
    monkeypatch.setattr(core, "SECRET_KEY", "ein-anderer-schluessel")
    assert main._katalog_name(BILD) != vorher


def test_ausliefern_lehnt_krumme_namen_ab(ctx):
    for name in ("../../etc/passwd", "kurz.jpg", "x" * 64 + ".png"):
        assert ctx.get(f"/catalog/{name}").status_code == 404


# ------------------------------------------------------ Ablauf

def test_bild_wird_geholt_und_ausgeliefert(ctx, monkeypatch):
    monkeypatch.setattr(integrations, "fetch_catalog_image",
                        lambda url, hosts=None: b"ROH")
    monkeypatch.setattr(integrations, "prepare_image",
                        lambda roh, max_side=400: b"\xff\xd8KLEIN")
    r = ctx.get("/catalog", params={"u": BILD})
    assert r.status_code == 200 and r.content == b"\xff\xd8KLEIN"
    assert "max-age=31536000" in r.headers["cache-control"]


def test_zweiter_abruf_geht_nicht_mehr_nach_draussen(ctx, monkeypatch):
    rufe = []

    def fake(url, hosts=None):
        rufe.append(url)
        return b"ROH"

    monkeypatch.setattr(integrations, "fetch_catalog_image", fake)
    monkeypatch.setattr(integrations, "prepare_image",
                        lambda roh, max_side=400: b"\xff\xd8K")
    ctx.get("/catalog", params={"u": BILD})
    ctx.get("/catalog", params={"u": BILD})
    assert len(rufe) == 1        # genau darum geht es


def test_fehlschlag_wird_nicht_gemerkt(ctx, monkeypatch):
    """Ein Aussetzer beim CDN darf ein Bild nicht dauerhaft verschwinden
    lassen – sonst bliebe die Karte für immer leer."""
    zustand = {"kaputt": True}

    def fake(url, hosts=None):
        if zustand["kaputt"]:
            raise RuntimeError("CDN weg")
        return b"ROH"

    monkeypatch.setattr(integrations, "fetch_catalog_image", fake)
    monkeypatch.setattr(integrations, "prepare_image",
                        lambda roh, max_side=400: b"\xff\xd8K")
    assert ctx.get("/catalog", params={"u": BILD}).status_code == 404
    zustand["kaputt"] = False
    assert ctx.get("/catalog", params={"u": BILD}).status_code == 200


# ------------------------------------------------------ Bestand nachholen

def test_status_zaehlt_nur_fremde_adressen(ctx):
    _eintrag(BILD, "sw0001a")
    _eintrag("/uploads/" + "a" * 32 + ".jpg", "custom-001")
    _eintrag("", "manuell-001")
    s = ctx.get("/api/images/status").json()
    assert s["total"] == 1 and s["pending"] == 1


def test_holen_arbeitet_den_bestand_ab(ctx, monkeypatch):
    _eintrag(BILD, "sw0001a")
    _eintrag("https://cdn.rebrickable.com/media/sets/10179-1.jpg", "10179-1")
    monkeypatch.setattr(integrations, "fetch_catalog_image",
                        lambda url, hosts=None: b"ROH")
    monkeypatch.setattr(integrations, "prepare_image",
                        lambda roh, max_side=400: b"\xff\xd8K")
    res = ctx.post("/api/images/fetch?limit=25").json()
    assert res["fetched"] == 2 and res["remaining"] == 0
    assert ctx.get("/api/images/status").json()["pending"] == 0


def test_holen_ist_admin_sache(ctx):
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('gast', 'x', 0, 0, ?)", (int(time.time()),))
        uid = cur.lastrowid
    ctx.headers["Authorization"] = "Bearer " + core.create_token(uid, "gast", False)
    assert ctx.post("/api/images/fetch").status_code == 403
