"""Zu klein abgelegte Katalogbilder holen sich selbst nach.

Bis 2.87.1 wurde mit 400 Pixeln abgelegt – das reichte, solange das Popup
eine Briefmarke von 72 Pixeln zeigte. Seit es mit dem Bild über die volle
Breite aufmacht, sind 400 zu wenig; schon abgelegte Bilder blieben aber
klein.

Nachgeholt wird, wenn jemand die Figur oder das Set **aufruft** – also beim
vollen Bild, nicht beim Daumennagel im Raster. Wer durch 800 Karten
blättert, löst nichts aus; sonst stünden bei jedem Blick in die Sammlung
Hunderte Abrufe an.

**Richtigstellung zum Tageskontingent (2.88.15):** Bis 2.88.14 stand hier
und im Changelog, ein Sammellauf ginge gegen dasselbe BrickLink-Kontingent
wie die Preise. Das stimmt nicht – Bilder kommen von den CDNs
(`img.bricklink.com`, `cdn.rebrickable.com`), das Tageslimit von 5000 gilt
für `api.bricklink.com`. Mit dem falschen Argument war die bessere Lösung
verworfen worden: „Bilder holen" in den Einstellungen zählt die zu kleinen
jetzt mit.
"""
import io
import time
from pathlib import Path

import pytest
from PIL import Image

import core
import main
from fastapi.testclient import TestClient

ADRESSE = "https://img.bricklink.com/ItemImage/MN/0/sw0402.png"


def _bild(kante: int) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", (kante, kante), (120, 60, 60)).save(puffer, "JPEG")
    return puffer.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "d.db"))
    core.init_db()
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('anna', 'x', 1, 0, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    return c


@pytest.fixture
def altes_bild(client):
    """Ein Bild, wie es vor 2.88.0 abgelegt wurde: 400 Pixel."""
    pfad = Path(main._katalog_dir()) / main._katalog_name(ADRESSE)
    pfad.write_bytes(_bild(400))
    return pfad


def test_das_volle_bild_stoesst_das_nachholen_an(client, altes_bild, monkeypatch):
    geholt = []

    def falscher_abruf(url, hosts):
        geholt.append(url)
        return _bild(800)

    monkeypatch.setattr(main.integrations, "fetch_catalog_image", falscher_abruf)
    r = client.get("/catalog", params={"u": ADRESSE})
    assert r.status_code == 200
    # Der Abruf läuft im Hintergrund – der Aufrufer bekommt diesmal noch das
    # alte Bild, damit sich das Fenster nicht aufhält.
    for _ in range(50):
        if geholt:
            break
        time.sleep(0.05)
    assert geholt == [ADRESSE]
    for _ in range(50):
        with Image.open(altes_bild) as b:
            if max(b.size) == 800:
                break
        time.sleep(0.05)
    with Image.open(altes_bild) as b:
        assert max(b.size) == 800


def test_der_daumennagel_stoesst_nichts_an(client, altes_bild, monkeypatch):
    """Sonst löste ein Blick auf die Sammlung 800 Abrufe aus."""
    geholt = []
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: geholt.append(url) or _bild(800))
    r = client.get("/catalog", params={"u": ADRESSE, "s": 160})
    assert r.status_code == 200
    time.sleep(0.4)
    assert geholt == []


def test_ein_grosses_bild_wird_nicht_noch_einmal_geholt(client, monkeypatch):
    """Sonst holte jedes Öffnen dasselbe Bild erneut – ein Abruf beim CDN
    für nichts, und das bei jedem Blick in den Steckbrief."""
    pfad = Path(main._katalog_dir()) / main._katalog_name(ADRESSE)
    pfad.write_bytes(_bild(main.BILD_KANTE))
    geholt = []
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: geholt.append(url) or _bild(800))
    assert client.get("/catalog", params={"u": ADRESSE}).status_code == 200
    time.sleep(0.4)
    assert geholt == []


def test_die_alten_daumennaegel_verschwinden(client, altes_bild, monkeypatch):
    """Sie stammen vom kleinen Bild – blieben sie liegen, sähe die Sammlung
    weiter ausgefranst aus."""
    daumen = Path(str(altes_bild) + ".160.jpg")
    daumen.write_bytes(_bild(160))
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: _bild(800))
    client.get("/catalog", params={"u": ADRESSE})
    for _ in range(50):
        if not daumen.exists():
            break
        time.sleep(0.05)
    assert not daumen.exists()


def test_bilder_holen_schaerft_die_alten_mit(client, altes_bild, monkeypatch):
    """„Bilder holen" holte nur, was ganz fehlte.

    Die alten 400er blieben liegen und wurden erst scharf, wenn jemand den
    Artikel öffnete – bei 780 Figuren dauert das seine Zeit. Seit 2.88.15
    gelten sie als offen und werden mitgeholt.
    """
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, img_url,"
            " quantity, condition, added_by, added_at)"
            " VALUES ('sw0402', 'minifig', 'Test', ?, 1, 'used', 1, ?)",
            (ADRESSE, int(time.time())))
    assert client.get("/api/images/status").json()["pending"] == 1

    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: _bild(800))
    r = client.post("/api/images/fetch", params={"limit": 5})
    assert r.status_code == 200 and r.json()["fetched"] == 1
    with Image.open(altes_bild) as b:
        assert max(b.size) == 800
    assert client.get("/api/images/status").json()["pending"] == 0


def test_ein_grosses_bild_gilt_nicht_als_offen(client, monkeypatch):
    """Sonst liefe der Lauf endlos über dieselben Bilder."""
    pfad = Path(main._katalog_dir()) / main._katalog_name(ADRESSE)
    pfad.write_bytes(_bild(main.BILD_KANTE))
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, img_url,"
            " quantity, condition, added_by, added_at)"
            " VALUES ('sw0402', 'minifig', 'Test', ?, 1, 'used', 1, ?)",
            (ADRESSE, int(time.time())))
    assert client.get("/api/images/status").json()["pending"] == 0


def test_eine_kleine_quelle_wird_nicht_ewig_wieder_geholt(client, altes_bild,
                                                          monkeypatch):
    """**Größer als die Quelle geht nicht.**

    Von BrickLink kommen die meisten Figurenbilder mit 400 Pixeln –
    nachgemessen am 23.09.2026: von 100 frisch geholten waren 91 genau 400
    groß. `prepare_image` verkleinert nur, es erfindet keine Pixel. Ohne
    eine Merkdatei hätte jeder Lauf dieselben Bilder wieder und wieder
    geholt, weil sie hinterher genauso klein sind wie vorher – eine Instanz
    lief genau in diese Schleife.
    """
    geholt = []
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: geholt.append(url) or _bild(400))
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, img_url,"
            " quantity, condition, added_by, added_at)"
            " VALUES ('sw0402', 'minifig', 'Test', ?, 1, 'used', 1, ?)",
            (ADRESSE, int(time.time())))
    assert client.get("/api/images/status").json()["pending"] == 1
    client.post("/api/images/fetch", params={"limit": 5})
    assert len(geholt) == 1
    # Das Bild ist immer noch 400 – aber es gilt als erledigt.
    with Image.open(altes_bild) as b:
        assert max(b.size) == 400
    assert client.get("/api/images/status").json()["pending"] == 0
    client.post("/api/images/fetch", params={"limit": 5})
    assert len(geholt) == 1, "kein zweiter Abruf für dieselbe Datei"


def test_eine_groessere_zielgroesse_hebt_die_marke_auf(client, altes_bild,
                                                       monkeypatch):
    """Wird später größer abgelegt, darf alles noch einmal versucht werden."""
    monkeypatch.setattr(main.integrations, "fetch_catalog_image",
                        lambda url, hosts: _bild(400))
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, img_url,"
            " quantity, condition, added_by, added_at)"
            " VALUES ('sw0402', 'minifig', 'Test', ?, 1, 'used', 1, ?)",
            (ADRESSE, int(time.time())))
    client.post("/api/images/fetch", params={"limit": 5})
    assert client.get("/api/images/status").json()["pending"] == 0
    monkeypatch.setattr(main, "BILD_KANTE", 1200)
    assert client.get("/api/images/status").json()["pending"] == 1
