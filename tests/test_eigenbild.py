"""Das eigene Scan-Foto **zusätzlich** am Artikel.

Wie die Bilder, die Käufer bei BrickLink beisteuern: Das Katalogbild bleibt
das erste, was man sieht, das eigene Foto kommt in der Galerie daneben. Es
hängt am Artikel, nicht an der einzelnen Sammlungszeile – wer dieselbe Figur
zweimal hat, hat auch zweimal dieselben Fotos.
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


def test_das_katalogbild_bleibt_unangetastet():
    """Der Kern der Sache: zusätzlich, nicht statt."""
    quelle = js()
    anfang = quelle.index("async function eigenbildAnhaengen(")
    koerper = quelle[anfang:quelle.index("\n}", anfang)]
    assert "it.img_url =" not in koerper, "img_url darf nicht ersetzt werden"
    assert '"/item_photos"' in koerper


def test_ohne_schalter_passiert_nichts():
    quelle = js()
    anfang = quelle.index("async function eigenbildAnhaengen(")
    koerper = quelle[anfang:quelle.index("\n}", anfang)]
    assert "if (!eigenbildAn" in koerper


def test_hochgeladen_wird_erst_beim_anlegen():
    """Wer nur schaut, soll nichts hochladen."""
    quelle = js()
    anfang = quelle.index("function renderScanResults(")
    koerper = quelle[anfang:anfang + 6000]
    assert "wireWantButtons(box, items, eigenbildAnhaengen)" in koerper
    assert "wireCartButtons(box, items, eigenbildAnhaengen)" in koerper
    posten = quelle.index('await api("/collection", { method: "POST"', anfang)
    assert "eigenbildAnhaengen(it," in quelle[posten - 300:posten]


def test_nur_foto_ohne_alles_andere():
    """Für Artikel, die längst in der Sammlung stehen: nur das Foto dazu,
    ohne eine zweite Zeile anzulegen."""
    quelle = js()
    assert 'data-foto="${i}"' in quelle
    anfang = quelle.index('box.querySelectorAll("[data-foto]")')
    koerper = quelle[anfang:anfang + 900]
    assert "eigenbildAnhaengen(it, i, true)" in koerper, (
        "der Knopf muss auch ohne das Kästchen wirken")
    # Und er legt nichts an.
    for verboten in ('api("/collection"', 'api("/wanted"', "addToList("):
        assert verboten not in koerper, verboten


def test_kaestchen_gilt_nur_fuers_anlegen():
    """Ohne Haken und ohne Zwang passiert nichts – sonst käme beim bloßen
    Anlegen ungefragt ein Foto mit."""
    quelle = js()
    anfang = quelle.index("async function eigenbildAnhaengen(")
    koerper = quelle[anfang:quelle.index("\n}", anfang)]
    assert "if (!eigenbildAn && !erzwingen) return;" in koerper


def test_ohne_foto_kein_knopf():
    """Ohne Scan-Foto wäre der Knopf eine Sackgasse."""
    quelle = js()
    stelle = quelle.index('data-foto="${i}"')
    assert "lastScanFile ?" in quelle[stelle - 200:stelle]


def test_jeder_treffer_bekommt_seinen_ausschnitt():
    quelle = js()
    anfang = quelle.index("async function eigenbildAnhaengen(")
    koerper = quelle[anfang:quelle.index("\n}", anfang)]
    assert "scanBoxen[i]" in koerper and "ausschnittBild(" in koerper
    assert "lastScanFile" in koerper


def test_alle_erkennungswege_fuehren_rahmen_mit():
    quelle = js()
    assert len(re.findall(r"\n\s*scanBoxen = ", quelle)) >= 6


def test_neues_foto_verwirft_alte_rahmen():
    quelle = js()
    anfang = quelle.index("async function handlePhoto(")
    assert "scanBoxen = [];" in quelle[anfang:anfang + 600]


def test_katalogsuche_haengt_kein_scanfoto_an():
    quelle = js()
    aufrufe = re.findall(r"(?<!function )wire(?:Want|Cart)Buttons"
                         r"\(box, items([^)]*)\)", quelle)
    assert len(aufrufe) == 4, f"unerwartet viele Aufrufe: {aufrufe}"
    mit_foto = [a for a in aufrufe if "eigenbildAnhaengen" in a]
    ohne = [a for a in aufrufe if "eigenbildAnhaengen" not in a]
    assert len(mit_foto) == 2
    assert all(a.strip() == "" for a in ohne), (
        f"Außerhalb des Scans darf kein Foto angehängt werden: {ohne}")


def test_galerie_kann_eigene_fotos_wieder_loesen():
    quelle = js()
    assert "async function eigenesFotoEntfernen(" in quelle
    assert 'gallery.eigene' in quelle


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


def _hochladen(client, farbe=(200, 30, 30)):
    return client.post("/api/upload_image",
                       files={"file": ("scan.jpg", _bild(farbe), "image/jpeg")}
                       ).json()["url"]


def test_hochladen_liefert_eine_adresse(client):
    url = _hochladen(client)
    assert re.fullmatch(r"/uploads/[0-9a-f]{32}\.jpg", url)


def test_bild_wird_verkleinert_und_ist_abrufbar(client):
    """Ein Handyfoto darf die Platte nicht vollschreiben."""
    r = client.get(_hochladen(client))
    assert r.status_code == 200
    assert max(Image.open(io.BytesIO(r.content)).size) <= 800


def test_foto_haengt_am_artikel(client):
    url = _hochladen(client)
    r = client.post("/api/item_photos", json={
        "item_type": "minifig", "item_id": "sw0978", "url": url})
    assert r.status_code == 200
    d = client.get("/api/images/minifig/sw0978").json()
    assert [f["url"] for f in d["own"]] == [url]
    assert url in d["images"]


def test_zweimal_dasselbe_foto_bleibt_eins(client):
    url = _hochladen(client)
    for _ in range(2):
        client.post("/api/item_photos", json={
            "item_type": "minifig", "item_id": "sw0978", "url": url})
    assert len(client.get("/api/images/minifig/sw0978").json()["own"]) == 1


def test_mehrere_fotos_je_artikel(client):
    for farbe in ((200, 30, 30), (30, 200, 30), (30, 30, 200)):
        client.post("/api/item_photos", json={
            "item_type": "minifig", "item_id": "sw0978",
            "url": _hochladen(client, farbe)})
    assert len(client.get("/api/images/minifig/sw0978").json()["own"]) == 3


def test_fremde_adressen_werden_abgewiesen(client):
    """Sonst holte die Galerie beim Anschauen unbemerkt etwas von außen."""
    for url in ("https://example.invalid/bild.jpg", "/uploads/../geheim.jpg",
                "/uploads/nicht-hex.jpg", "/static/app.js"):
        r = client.post("/api/item_photos", json={
            "item_type": "minifig", "item_id": "sw0978", "url": url})
        assert r.status_code in (400, 404, 422), url
    assert client.get("/api/images/minifig/sw0978").json()["own"] == []


def test_foto_ohne_datei_wird_abgewiesen(client):
    r = client.post("/api/item_photos", json={
        "item_type": "minifig", "item_id": "sw0978",
        "url": "/uploads/" + "0" * 32 + ".jpg"})
    assert r.status_code == 404


def test_entfernen_loest_nur_die_verbindung(client):
    """Die Datei bleibt – sie kann an einem anderen Artikel hängen."""
    url = _hochladen(client)
    client.post("/api/item_photos", json={
        "item_type": "minifig", "item_id": "sw0111", "url": url})
    pid = client.post("/api/item_photos", json={
        "item_type": "minifig", "item_id": "sw0222", "url": url}).json()["id"]
    assert client.delete(f"/api/item_photos/{pid}").status_code == 200
    assert client.get("/api/images/minifig/sw0222").json()["own"] == []
    # Am anderen Artikel hängt es weiter, und die Datei ist noch da.
    assert len(client.get("/api/images/minifig/sw0111").json()["own"]) == 1
    assert client.get(url).status_code == 200


def test_katalogbild_bleibt_das_erste(client):
    """Das eigene Foto kommt daneben, nicht davor."""
    url = _hochladen(client)
    client.post("/api/item_photos", json={
        "item_type": "minifig", "item_id": "sw0978", "url": url})
    bilder = client.get("/api/images/minifig/sw0978").json()["images"]
    assert bilder[-1] == url
    assert len(bilder) > 1, "ohne Katalogbild sagt der Test nichts"


def test_fotos_gehen_in_die_sicherung(client):
    url = _hochladen(client)
    client.post("/api/item_photos", json={
        "item_type": "minifig", "item_id": "sw0978", "url": url})
    dump = client.get("/api/backup").json()
    assert dump["tables"]["item_photos"][0]["url"] == url


def test_arbeitsbild_wird_wieder_freigegeben():
    """Das entpackte Foto liegt außerhalb des JS-Speichers – in der Kurve
    sieht man davon nichts, im Renderer ist es trotzdem da. Der Foto-Weg war
    der einzige, der es nie wieder losließ."""
    quelle = js()
    anfang = quelle.index("async function eigenbildAnhaengen(")
    koerper = quelle[anfang:quelle.index("\n}", anfang)]
    assert "arbeitBildSpaeterFreigeben()" in koerper


def test_ausschnitt_immer_mit_freigabe():
    """Jede Stelle, die `ausschnittBild` ohne fertiges Arbeitsbild aufruft,
    muss es auch wieder loslassen – sonst bleibt es bis zum nächsten Foto."""
    quelle = js()
    for stelle in re.finditer(r"await ausschnittBild\(([^)]*)\)", quelle):
        if "," in stelle.group(1):
            continue                      # bekommt das Arbeitsbild gereicht
        umfeld = quelle[stelle.start():stelle.start() + 700]
        assert "arbeitBildFreigeben()" in umfeld \
            or "arbeitBildSpaeterFreigeben()" in umfeld, stelle.group(0)


def test_ansichtswechsel_raeumt_auf():
    """Wer den Scan-Tab verlässt, lässt nichts Entpacktes zurück.

    Geprüft wird die Absicht, nicht der Wortlaut: Beides liegt außerhalb
    des JS-Speichers und taucht in keiner Messung auf, also muss es an
    dieser Grenze weg. Die Reihum-Zeichenfläche kam am 29.08.2026 dazu –
    sie blieb liegen, sobald „Weitersuchen" angeboten wurde, und wanderte
    dann durch alle Ansichten mit.
    """
    quelle = js()
    anfang = quelle.index("function showTab(")
    koerper = quelle[anfang:anfang + 1600]
    bedingung = koerper.index('name !== "scan"')
    danach = koerper[bedingung:bedingung + 500]
    assert "arbeitBildFreigeben()" in danach
    assert "reihumAufraeumen()" in danach
    # Nicht mitten in einer laufenden Suche: Die Schleife zeichnet aus
    # genau dieser Fläche.
    assert "reihumLaeuft" in danach
