"""Karten holen kleine Bilder, nicht die vollen.

Der Browser **entpackt** jedes Bild in voller Größe, egal wie klein es
dargestellt wird. Abgelegt wurde mit 400 px, angezeigt wird in den Karten
mit 72 – bei 130 Karten lagen so rund 80 MB entpackte Bilder im Fenster,
und zwar außerhalb des JS-Speichers, wo keine Messung sie sieht. Genau die
Art unsichtbarer Last, die einen Tab umbringt, während die Kurve flach
bleibt.
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

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
ADRESSE = "https://img.bricklink.com/ItemImage/MN/0/sw0402.png"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "d.db"))
    core.init_db()
    # Ein „Katalogbild" von 400 px ablegen, ohne nach draußen zu gehen.
    puffer = io.BytesIO()
    Image.new("RGB", (400, 400), (180, 60, 60)).save(puffer, "JPEG")
    pfad = Path(main._katalog_dir()) / main._katalog_name(ADRESSE)
    pfad.write_bytes(puffer.getvalue())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 0, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def masse(antwort) -> tuple:
    return Image.open(io.BytesIO(antwort.content)).size


def test_ohne_angabe_kommt_die_volle_fassung(client):
    r = client.get("/catalog", params={"u": ADRESSE})
    assert r.status_code == 200
    assert masse(r) == (400, 400)


def test_mit_angabe_kommt_der_daumennagel(client):
    r = client.get("/catalog", params={"u": ADRESSE, "s": 160})
    assert r.status_code == 200
    assert max(masse(r)) == 160


def test_der_daumennagel_wird_nur_einmal_erzeugt(client):
    client.get("/catalog", params={"u": ADRESSE, "s": 160})
    dateien = list(Path(main._katalog_dir()).glob("*.160.jpg"))
    assert len(dateien) == 1
    zuerst = dateien[0].stat().st_mtime_ns
    client.get("/catalog", params={"u": ADRESSE, "s": 160})
    assert dateien[0].stat().st_mtime_ns == zuerst, "wurde neu erzeugt"


def test_freie_groessen_werden_nicht_bedient(client):
    """Sonst könnte jemand mit 500 Anfragen 500 Dateien erzeugen lassen."""
    for unerlaubt in (32, 199, 4000):
        r = client.get("/catalog", params={"u": ADRESSE, "s": unerlaubt})
        assert r.status_code == 200
        assert masse(r) == (400, 400), f"{unerlaubt} hätte nicht greifen dürfen"
    assert not list(Path(main._katalog_dir()).glob("*.32.jpg"))


def test_ein_fehlendes_bild_bleibt_ein_fehlendes_bild(client):
    r = client.get("/catalog", params={"u": "https://img.bricklink.com/x.png",
                                       "s": 160})
    assert r.status_code == 404


# ---------------------------------------------------------------- Oberfläche

def test_alle_karten_holen_klein():
    """Bliebe eine Stelle auf der vollen Fassung, trüge die Ansicht sie
    weiterhin mit."""
    quelle = js()
    stellen = re.findall(r'<img class="card-img" src="\$\{imgSrc\(([^)]*)\)\}',
                         quelle)
    assert stellen, "keine Kartenbilder gefunden"
    ohne = [s for s in stellen if "true" not in s]
    assert not ohne, f"holen noch die volle Fassung: {ohne}"


def test_die_grossansicht_nimmt_die_volle_fassung():
    quelle = js()
    assert "function imgGross(" in quelle
    assert "openGallery(imgGross(img.src)" in quelle


def test_die_kante_passt_zur_anzeige():
    """72 px Anzeige, auf Retina also 144 – die Kante muss darüber liegen,
    sonst sieht es unscharf aus."""
    quelle = js()
    kante = re.search(r"const DAUMEN_KANTE = (\d+)", quelle)
    assert kante and 144 <= int(kante.group(1)) <= 220
    assert int(kante.group(1)) in main.DAUMEN_GROESSEN, (
        "die Oberfläche fragt eine Größe, die der Server nicht bedient")
