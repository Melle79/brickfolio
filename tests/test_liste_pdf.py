"""Listen als PDF (3.2.1): Einkaufs- oder Verkaufsliste, vom Server gebaut."""
import time

import pytest
from fastapi.testclient import TestClient

import core
import listen_pdf
import main


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "d.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        profi = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)", (now,)).lastrowid
        kind = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('kind', 'x', 0, 0, ?)", (now,)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(profi, "admin", True)
    k = TestClient(main.app)
    k.headers["Authorization"] = "Bearer " + core.create_token(kind, "kind", False)
    lid = c.post("/api/lists", json={"name": "Flohmarkt/Süd"}).json()["id"]
    for nr, bezahlt in (("sw0001", 4.0), ("sw0002", None)):
        c.post(f"/api/lists/{lid}/items", json={
            "item_id": nr, "item_type": "minifig", "name": "Figur " + nr,
            "qty": 2, "condition": "used", "paid_price": bezahlt})
    with core.db() as conn:
        conn.execute("UPDATE shopping_items SET price_used = 5.0, price_new = 8.0")
        conn.execute("UPDATE shopping_items SET done = 1 WHERE item_id = 'sw0002'")
    return c, k, lid


@pytest.fixture
def mitschnitt(monkeypatch):
    """Was an `erzeugen` geht – der Inhalt eines PDFs ist komprimiert und
    lässt sich schlecht durchsuchen, die Übergabe schon."""
    aufrufe = []
    echt = listen_pdf.erzeugen

    def erzeugen(liste, items, **kw):
        aufrufe.append((liste, [dict(i) for i in items], kw))
        return echt(liste, items, **{**kw, "bild_fuer": None})
    monkeypatch.setattr(listen_pdf, "erzeugen", erzeugen)
    return aufrufe


def test_einkaufsliste_als_pdf(ctx, mitschnitt):
    c, _, lid = ctx
    r = c.get(f"/api/lists/{lid}/pdf?art=einkauf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    # Schrägstrich raus, Umlaut bleibt (UTF-8 im Dateinamen).
    assert "Einkaufsliste%20FlohmarktS%C3%BCd.pdf" in r.headers["content-disposition"]
    _, items, kw = mitschnitt[0]
    assert kw["profi"] is True
    assert sorted(i["paid_price"] or 0 for i in items) == [0, 4.0]


def test_standard_benutzer_sieht_keine_einkaufspreise(ctx, mitschnitt):
    _, k, lid = ctx
    assert k.get(f"/api/lists/{lid}/pdf").status_code == 200
    _, items, kw = mitschnitt[0]
    assert kw["profi"] is False
    assert all(i["paid_price"] is None for i in items)


def test_verkaufsliste_und_englisch(ctx, mitschnitt):
    c, _, lid = ctx
    r = c.get(f"/api/lists/{lid}/pdf?art=verkauf&prozent=90&sprache=en")
    assert r.status_code == 200
    assert "Sales%20list" in r.headers["content-disposition"]
    assert mitschnitt[0][2]["prozent"] == 90


def test_unbekannte_fassung_und_liste(ctx):
    c, _, lid = ctx
    assert c.get(f"/api/lists/{lid}/pdf?art=quatsch").status_code == 422
    assert c.get("/api/lists/9999/pdf").status_code == 404


def test_archiv_nur_fuer_profis(ctx):
    c, k, lid = ctx
    with core.db() as conn:
        conn.execute("UPDATE shopping_lists SET archived = 1")
    assert k.get(f"/api/lists/{lid}/pdf").status_code == 403
    assert c.get(f"/api/lists/{lid}/pdf").status_code == 200


def test_viele_artikel_lange_namen_und_sonderzeichen():
    """Seitenumbruch mit wiederholtem Tabellenkopf, umbrechende Namen und
    Zeichen außerhalb von Latin-1 (Rückfallschrift)."""
    items = [{"item_id": f"sw{n:04d}", "item_type": "minifig" if n % 5 else "set",
              "name": ("Clone Trooper Commander Gree, 41st Elite Corps (Phase 1) "
                       "- Large Eyes, Łódź-Druck " * (1 + n % 2)).strip(),
              "qty": 1 + n % 3, "condition": "new" if n % 2 else "used",
              "price_new": 12.5, "price_used": 7.25, "paid_price": 3.0 if n % 4 else None,
              "done": n % 7 == 0} for n in range(1, 75)]
    for art in ("einkauf", "verkauf"):
        pdf = listen_pdf.erzeugen({"name": "Große Liste – €"}, items, art=art,
                                  prozent=85, absender="Dein Nupplo")
        assert pdf.startswith(b"%PDF") and len(pdf) > 5000


@pytest.mark.parametrize("sprache, erwartet", [("de", "1.234,50 €"), ("en", "€1,234.50")])
def test_geld(sprache, erwartet):
    assert listen_pdf.geld(1234.5, "EUR", sprache) == erwartet


def test_verkaufsliste_rechnet_mit_anteil():
    assert listen_pdf.wert({"condition": "new", "price_new": None, "price_used": 4}) == 4
    assert listen_pdf.wert({"condition": "used", "price_new": 9, "price_used": 5}) == 5
