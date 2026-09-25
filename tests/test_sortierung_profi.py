"""Sortieren nach Kaufpreis und Gewinn – nur für Sammlerprofis.

Seit 2.90.7. Gewünscht am 25.09.2026: Ein Tausch mit 999,99 € Kaufpreis stand
unter „Wert (hoch → niedrig)“ nicht vorn, weil Wert der Marktwert ist. Wer
nach dem Bezahlten sucht, bekommt jetzt eine eigene Sortierung.
"""
import time

import pytest
from fastapi.testclient import TestClient

import core
import main


def _client(tmp_path, monkeypatch, dealer):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "sort.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer, "
            "created_at) VALUES ('anna', 'x', 1, ?, ?)",
            (dealer, int(time.time()))).lastrowid
        # Name, Menge, Marktwert gebraucht, bezahlt
        for nr, name, menge, wert, bezahlt in (
                ("sw1", "Teuer gekauft", 1, 10.0, 50.0),
                ("sw2", "Schnäppchen", 2, 30.0, 5.0),
                ("sw3", "Ohne Kaufpreis", 1, 99.0, None),
                ("sw4", "Mittel", 1, 20.0, 15.0)):
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity, "
                "condition, price_used, paid_price, added_at) VALUES "
                "(?, 'minifig', ?, ?, 'used', ?, ?, ?)",
                (nr, name, menge, wert, bezahlt, int(time.time())))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    return c


def _reihe(c, sort):
    return [x["item_id"] for x in
            c.get(f"/api/collection?sort={sort}").json()["items"]]


def test_paid_desc(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, 1)
    assert _reihe(c, "paid_desc") == ["sw1", "sw4", "sw2", "sw3"]


def test_profit_both_ways(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, 1)
    # Gewinn: sw2 = 60 - 5 = 55, sw4 = 5, sw1 = -40, sw3 ohne Kaufpreis ans Ende
    assert _reihe(c, "profit_desc") == ["sw2", "sw4", "sw1", "sw3"]
    assert _reihe(c, "profit_asc") == ["sw1", "sw4", "sw2", "sw3"]


def test_normal_users_do_not_get_it(tmp_path, monkeypatch):
    """Schon die Reihenfolge verriete, was bezahlt wurde."""
    c = _client(tmp_path, monkeypatch, 0)
    assert _reihe(c, "paid_desc") == _reihe(c, "added")
    assert c.post("/api/me/sort", json={"sort": "paid_desc"}).status_code == 403


def test_dealer_can_save_it_as_default(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, 1)
    assert c.post("/api/me/sort", json={"sort": "profit_desc"}).status_code == 200
