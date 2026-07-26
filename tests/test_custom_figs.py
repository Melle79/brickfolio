"""Tests für eigene Figuren (Custom): Bild-Upload, Ausliefern und dass
custom-Nummern von Katalog-/Preisabfragen übersprungen werden."""
import io
import time

import pytest
from PIL import Image

import core
import integrations
import main
from fastapi.testclient import TestClient


def _png(size=(60, 40), color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "c.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_upload_returns_url_and_serves_image(client):
    r = client.post("/api/upload_image",
                    files={"file": ("fig.png", _png(), "image/png")})
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("/uploads/") and url.endswith(".jpg")

    # Bild ist ohne Login abrufbar (wie andere Katalogbilder)
    plain = TestClient(main.app)
    img = plain.get(url)
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(img.content)).size[0] > 0


def test_large_images_are_scaled_down(client):
    r = client.post("/api/upload_image",
                    files={"file": ("big.png", _png((2400, 1800)), "image/png")})
    url = r.json()["url"]
    img = Image.open(io.BytesIO(TestClient(main.app).get(url).content))
    assert max(img.size) <= 800          # verkleinert, spart Platz


def test_upload_rejects_non_image(client):
    r = client.post("/api/upload_image",
                    files={"file": ("x.txt", b"kein Bild", "text/plain")})
    assert r.status_code == 400


def test_upload_rejects_empty(client):
    r = client.post("/api/upload_image",
                    files={"file": ("leer.png", b"", "image/png")})
    assert r.status_code == 400


def test_upload_needs_login():
    plain = TestClient(main.app)
    r = plain.post("/api/upload_image",
                   files={"file": ("fig.png", _png(), "image/png")})
    assert r.status_code == 401


def test_unknown_or_crafted_names_are_404():
    plain = TestClient(main.app)
    assert plain.get("/uploads/gibtsnicht.jpg").status_code == 404
    # kein Ausbrechen aus dem Ordner
    assert plain.get("/uploads/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_custom_numbers_skip_bricklink(client, monkeypatch):
    """custom-… ist keine BrickLink-Nummer: Sets/Teile bleiben leer, statt
    sinnlos abzufragen."""
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    called = []
    monkeypatch.setattr(integrations, "bricklink_supersets",
                        lambda no: called.append(no) or [])
    monkeypatch.setattr(integrations, "bricklink_minifig_parts",
                        lambda no: called.append(no) or [])
    assert client.get("/api/fig_sets/custom-eigen-001").json()["sets"] == []
    assert client.get("/api/fig_parts/custom-eigen-001").json()["items"] == []
    assert called == []                  # gar nicht erst angefragt


def test_custom_item_can_be_collected(client):
    """Eine eigene Figur landet normal in der Sammlung – mit eigenem Bild."""
    up = client.post("/api/upload_image",
                     files={"file": ("f.png", _png(), "image/png")}).json()
    r = client.post("/api/collection", json={
        "item_id": "custom-eigen-001", "item_type": "minifig",
        "name": "Sven-Ritter", "img_url": up["url"], "bricklink_url": "",
        "quantity": 1, "condition": "used"})
    assert r.status_code == 200
    row = client.get("/api/collection").json()["items"][0]
    assert row["item_id"] == "custom-eigen-001"
    assert row["img_url"] == up["url"]


def test_custom_sets_do_not_query_bricklink(client, monkeypatch):
    """Ein eigenes Set hat keinen BrickLink-Inhalt – die Abfrage entfällt."""
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    called = []
    monkeypatch.setattr(integrations, "bricklink_subsets",
                        lambda no: called.append(no) or [])
    assert client.get("/api/set_figs/custom-mein-set").json()["items"] == []
    assert client.get("/api/set_figs/manuell-123").json()["items"] == []
    assert called == []


# ------------------------------------------------- fortlaufende Nummern

def test_first_custom_number_is_001(client):
    assert client.get("/api/next_custom_id").json()["item_id"] == "custom-001"


def test_counts_up_across_tables(client):
    """Sammlung, Wunschliste und Einkaufslisten zählen gemeinsam hoch."""
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, added_at) VALUES ('custom-001', 'minifig', 'A', 1, "
            "'used', ?)", (now,))
        conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, added_at) "
            "VALUES ('custom-004', 'minifig', 'B', ?)", (now,))
        lid = conn.execute(
            "INSERT INTO shopping_lists (name, created_at) VALUES ('L', ?)",
            (now,)).lastrowid
        conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name, "
            "added_at) VALUES (?, 'custom-007', 'minifig', 'C', ?)", (lid, now))
    assert client.get("/api/next_custom_id").json()["item_id"] == "custom-008"


def test_own_scheme_does_not_break_counting(client):
    """Selbst vergebene Namen ohne Zahl stören die Zählung nicht."""
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, added_at) VALUES ('custom-ritter-blau', 'minifig', "
            "'A', 1, 'used', ?)", (now,))
    assert client.get("/api/next_custom_id").json()["item_id"] == "custom-001"


def test_gaps_are_not_reused(client):
    """Gezählt wird ab der höchsten Nummer, Lücken bleiben frei – sonst gäbe
    es zwei Figuren mit derselben internen Nummer in Notizen/Ausdrucken."""
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, added_at) "
            "VALUES ('custom-009', 'minifig', 'B', ?)", (now,))
    assert client.get("/api/next_custom_id").json()["item_id"] == "custom-010"
