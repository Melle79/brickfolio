"""Was passiert bei krummen Eingaben und gleichzeitigen Zugriffen.

Beides ist im Belastungstest aufgefallen: Der Server hat mit einem nackten
„Internal Server Error" geantwortet, wo eine Erklärung hingehört hätte.
"""
import threading
import time

import pytest

import core
import main
from fastapi.testclient import TestClient

KOPF = "Nummer,Typ,Name,Anzahl,Zustand\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "rob.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('sven', 'x', 1, 1, ?)",
                     (now,))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(1, "sven", True)
    return c


# ------------------------------------------------------------- Wegweiser

def test_keine_route_zeigt_auf_eine_hilfsfunktion():
    """Ein `@app.post(...)` direkt über der falschen Funktion fällt beim
    Lesen nicht auf – der Code sieht völlig normal aus.

    Genau das ist passiert: Beim Einbau der Schlüsselprüfung landete
    `_fremder_schluessel` zwischen dem Wegweiser für `/api/hub/trades` und
    dem Vorgang, der dort hingehört. Zwei Tage lang beantwortete eine interne
    Hilfsfunktion die Anfrage, und „Anfrage senden" endete in
    „Eingabe nicht gültig: Field required".

    Regel: Was mit `_` anfängt, ist Beiwerk und nie ein Endpunkt."""
    schlecht = []
    for r in main.app.routes:
        name = getattr(getattr(r, "endpoint", None), "__name__", "")
        if name.startswith("_"):
            schlecht.append(f"{sorted(getattr(r, 'methods', []))} "
                            f"{getattr(r, 'path', '?')} → {name}")
    assert not schlecht, "Route zeigt auf eine Hilfsfunktion: " + "; ".join(schlecht)


def test_anfrage_senden_erreicht_den_richtigen_vorgang(client, monkeypatch):
    """Der Weg, den der Knopf „Anfrage senden" nimmt."""
    monkeypatch.setattr(main.hub, "enabled", lambda: False)
    r = client.post("/api/hub/trades", json={
        "to": "bf_123", "item_id": "sw0312", "item_name": "TX-20",
        "text": "Hallo Paul, hättest du Interesse?"})
    # Ohne Hub ist 400 die richtige Antwort – 422 hieße, die Angaben kämen
    # gar nicht erst an der richtigen Stelle an.
    assert r.status_code == 400, r.text
    assert "Hub" in r.json()["detail"]


# ------------------------------------------------------------- CSV-Import

def test_offenes_anfuehrungszeichen_wird_erklaert(client):
    """Ein einzelnes „ ohne Gegenstück macht aus dem Rest der Datei ein Feld.
    Ab 128 KB bricht Python ab – das kam ungefiltert als Serverfehler an,
    und niemand konnte ahnen, dass ein Anführungszeichen schuld war."""
    # Der Rest muss die Feldgrenze von 128 KB überschreiten – erst dort gibt
    # Python auf. Darunter schluckt es die Datei als einen langen Namen.
    rest = "".join(f"{i}-9,Set,Rest {i} mit etwas mehr Text,1,Gebraucht\n"
                   for i in range(4000))
    assert len(rest) > 131072, "Testdaten zu klein für die Feldgrenze"
    kaputt = KOPF + '1-1,Set,"Anfang ohne Ende,1,Gebraucht\n' + rest
    r = client.post("/api/import/csv", json={"csv": kaputt})
    assert r.status_code == 400
    assert "Anführungszeichen" in r.json()["detail"]


def test_riesenfeld_stuerzt_nicht_ab(client):
    r = client.post("/api/import/csv",
                    json={"csv": KOPF + "1-1,Set," + "A" * 200000 + ",1,Gebraucht\n"})
    assert r.status_code == 400


def test_normale_datei_geht_weiterhin(client):
    """Die Absicherung darf gültige Dateien nicht mitreißen."""
    r = client.post("/api/import/csv",
                    json={"csv": KOPF + '2-1,Set,"Name, mit Komma",2,Neu\n'})
    assert r.status_code == 200 and r.json()["created"] == 1


# ------------------------------------------------- Gleichzeitiges Anlegen

def test_gleicher_artikel_gleichzeitig(client, monkeypatch):
    """Zwei Anfragen für denselben, noch nicht vorhandenen Artikel sehen
    beide „gibt es noch nicht". Eine legt an, die andere läuft in die
    eindeutige Bedingung – das war ein Serverfehler, und ihr Stück war weg.

    Damit das nicht vom Zufall abhängt, wird der andere Schreiber genau in
    die Lücke gesetzt: `themes.for_item` wird zwischen dem Nachsehen und dem
    Einfügen aufgerufen, also genau dort, wo die zweite Anfrage dazwischen
    käme."""
    körper = {"item_id": "75192-1", "item_type": "set", "name": "Falke",
              "quantity": 3, "condition": "used"}
    echt = main.themes.for_item

    def dazwischen(item_id, item_type):
        with core.db() as conn:
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity,"
                " condition, added_at) VALUES (?, ?, 'Falke', 5, 'used', ?)",
                (item_id, item_type, int(time.time())))
        monkeypatch.setattr(main.themes, "for_item", echt)   # nur einmal
        return echt(item_id, item_type)

    monkeypatch.setattr(main.themes, "for_item", dazwischen)
    r = client.post("/api/collection", json=körper)

    assert r.status_code == 200, r.text
    assert r.json()["merged"] is True
    with core.db() as conn:
        zeilen = conn.execute(
            "SELECT quantity FROM collection WHERE item_id = '75192-1'"
        ).fetchall()
    assert len(zeilen) == 1, "es darf nur eine Zeile geben"
    assert zeilen[0]["quantity"] == 8, "5 vom anderen + 3 eigene, nichts weg"


def test_gleicher_artikel_aus_acht_faeden(client):
    """Zusätzlich der grobe Test: acht gleichzeitige Anfragen, am Ende muss
    die Menge stimmen."""
    körper = {"item_id": "10179-1", "item_type": "set", "name": "UCS",
              "quantity": 1, "condition": "used"}
    ergebnisse = []
    start = threading.Barrier(8)

    def anlegen():
        start.wait()
        ergebnisse.append(client.post("/api/collection", json=körper).status_code)

    fäden = [threading.Thread(target=anlegen) for _ in range(8)]
    for f in fäden:
        f.start()
    for f in fäden:
        f.join()

    assert set(ergebnisse) == {200}, f"Statuscodes: {sorted(ergebnisse)}"
    with core.db() as conn:
        zeilen = conn.execute(
            "SELECT quantity FROM collection WHERE item_id = '10179-1'"
        ).fetchall()
    assert len(zeilen) == 1 and zeilen[0]["quantity"] == 8


# ------------------------------------------------------------- Eingaben

@pytest.mark.parametrize("typ", ["raumschiff", "../etc", "<script>", ""])
def test_erfundene_artikelart_wird_abgelehnt(client, typ):
    """`condition` wurde immer geprüft, `item_type` nicht – so landete
    „raumschiff" klaglos in der Datenbank und tauchte danach in Adressen
    und Auswertungen wieder auf."""
    r = client.post("/api/collection", json={
        "item_id": "x-1", "item_type": typ, "name": "X",
        "quantity": 1, "condition": "used"})
    assert r.status_code == 422


@pytest.mark.parametrize("art", ["minifig", "set", "part"])
def test_die_echten_arten_gehen_weiter(client, art):
    r = client.post("/api/collection", json={
        "item_id": f"{art}-1", "item_type": art, "name": "X",
        "quantity": 1, "condition": "used"})
    assert r.status_code == 200


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "file:///etc/passwd",
    "vbscript:msgbox",
])
def test_bildadresse_nur_mit_ordentlichem_schema(client, url):
    """Ausgeführt wurde davon nichts – die CSP hat es abgefangen und die App
    zeigte den Platzhalter. Trotzdem hat so etwas in der Datenbank nichts
    zu suchen."""
    r = client.post("/api/collection", json={
        "item_id": "y-1", "item_type": "set", "name": "Y", "quantity": 1,
        "condition": "used", "img_url": url})
    assert r.status_code == 422


@pytest.mark.parametrize("url", [
    "", "/uploads/" + "a" * 32 + ".jpg",
    "https://img.bricklink.com/ItemImage/MN/0/sw0001a.png",
    "http://beispiel.test/x.jpg",
])
def test_richtige_bildadressen_gehen_weiter(client, url):
    r = client.post("/api/collection", json={
        "item_id": "z-" + str(abs(hash(url)) % 999), "item_type": "set",
        "name": "Z", "quantity": 1, "condition": "used", "img_url": url})
    assert r.status_code == 200
