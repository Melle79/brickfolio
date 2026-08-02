"""Das eigene Scan-Foto als Bild des Artikels.

Der Weg dahin ist bewusst schmal: Alle drei Anlege-Wege (Sammlung, Merken,
Liste) schicken `it.img_url` mit. Wird die eine Stelle vor dem Anlegen
ersetzt, gilt das Foto überall – ohne dass die drei Wege es einzeln wissen
müssen.
"""
import io
import re
import time
from pathlib import Path

import pytest
from PIL import Image

import core
import main
from fastapi.testclient import TestClient

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def js() -> str:
    return APP_JS.read_text(encoding="utf-8")


# ---------------------------------------------------------------- Oberfläche

def test_schalter_wird_gefragt():
    """„Es sollte natürlich gefragt werden" – der Schalter ist sichtbar und
    steht standardmäßig aus."""
    quelle = js()
    assert 'id="scan-eigenbild"' in quelle
    assert 'localStorage.getItem(EIGENBILD_KEY) === "1"' in quelle


def test_ohne_schalter_passiert_nichts():
    quelle = js()
    anfang = quelle.index("async function eigenbildAnhaengen(")
    koerper = quelle[anfang:quelle.index("\n}", anfang)]
    assert "if (!eigenbildAn" in koerper


def test_hochgeladen_wird_erst_beim_anlegen():
    """Wer nur schaut, soll nichts hochladen – der Haken hängt an den
    Anlege-Wegen, nicht am Anzeigen der Treffer."""
    quelle = js()
    anfang = quelle.index("function renderScanResults(")
    koerper = quelle[anfang:anfang + 4000]
    assert "wireWantButtons(box, items, eigenbildAnhaengen)" in koerper
    assert "wireCartButtons(box, items, eigenbildAnhaengen)" in koerper
    # …und in der Sammlung direkt vor dem POST.
    posten = quelle.index('await api("/collection", { method: "POST"', anfang)
    davor = quelle[posten - 300:posten]
    assert "eigenbildAnhaengen(it," in davor


def test_jeder_treffer_bekommt_seinen_ausschnitt():
    quelle = js()
    anfang = quelle.index("async function eigenbildAnhaengen(")
    koerper = quelle[anfang:quelle.index("\n}", anfang)]
    assert "scanBoxen[i]" in koerper and "ausschnittBild(" in koerper
    # Ohne Rahmen das ganze Foto – sonst käme gar nichts an.
    assert "lastScanFile" in koerper


def test_alle_erkennungswege_fuehren_rahmen_mit():
    """Vier Wege führen zu Treffern; jeder muss die Rahmen dazu setzen,
    sonst bekäme der falsche Artikel den Ausschnitt eines anderen."""
    quelle = js()
    assert len(re.findall(r"\n\s*scanBoxen = ", quelle)) >= 6


def test_neues_foto_verwirft_alte_rahmen():
    quelle = js()
    anfang = quelle.index("async function handlePhoto(")
    assert "scanBoxen = [];" in quelle[anfang:anfang + 600]


def test_katalogsuche_haengt_kein_scanfoto_an():
    """Dort gibt es keins – der Haken darf nur aus dem Scan kommen."""
    quelle = js()
    # Nur die Aufrufe, nicht die Vereinbarungen der beiden Funktionen.
    aufrufe = re.findall(r"(?<!function )wire(?:Want|Cart)Buttons"
                         r"\(box, items([^)]*)\)", quelle)
    assert len(aufrufe) == 4, f"unerwartet viele Aufrufe: {aufrufe}"
    mit_foto = [a for a in aufrufe if "eigenbildAnhaengen" in a]
    ohne = [a for a in aufrufe if "eigenbildAnhaengen" not in a]
    assert len(mit_foto) == 2, "Scan-Treffer müssen den Haken bekommen"
    assert all(a.strip() == "" for a in ohne), (
        f"Außerhalb des Scans darf kein Foto angehängt werden: {ohne}")


# ------------------------------------------------------------------- Backend

def _bild(farbe=(200, 30, 30)) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", (1400, 900), farbe).save(puffer, format="JPEG")
    return puffer.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "eig.db"))
    core.init_db()
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_hochladen_liefert_eine_adresse(client):
    r = client.post("/api/upload_image",
                    files={"file": ("scan.jpg", _bild(), "image/jpeg")})
    assert r.status_code == 200
    assert re.fullmatch(r"/uploads/[0-9a-f]{32}\.jpg", r.json()["url"])


def test_bild_wird_verkleinert_und_ist_abrufbar(client):
    """Ein Handyfoto darf die Platte nicht vollschreiben."""
    url = client.post("/api/upload_image",
                      files={"file": ("scan.jpg", _bild(), "image/jpeg")}
                      ).json()["url"]
    r = client.get(url)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    bild = Image.open(io.BytesIO(r.content))
    assert max(bild.size) <= 800


def test_sammlungseintrag_haelt_das_eigene_bild(client):
    """Der Kern: Das Bild bleibt am Artikel hängen, nicht nur am Upload."""
    url = client.post("/api/upload_image",
                      files={"file": ("scan.jpg", _bild(), "image/jpeg")}
                      ).json()["url"]
    r = client.post("/api/collection", json={
        "item_id": "sw0978", "item_type": "minifig", "name": "Luke",
        "img_url": url, "condition": "used"})
    assert r.status_code == 200
    eintrag = client.get("/api/collection").json()["items"][0]
    assert eintrag["img_url"] == url


def test_zwei_ausschnitte_werden_zwei_bilder(client):
    """Bei mehreren Figuren darf nicht eins für alle herhalten."""
    a = client.post("/api/upload_image",
                    files={"file": ("a.jpg", _bild((10, 200, 10)), "image/jpeg")}
                    ).json()["url"]
    b = client.post("/api/upload_image",
                    files={"file": ("b.jpg", _bild((10, 10, 200)), "image/jpeg")}
                    ).json()["url"]
    assert a != b
    assert client.get(a).content != client.get(b).content
