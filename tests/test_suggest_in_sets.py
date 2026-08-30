"""`in_sets` nennt auch den Zustand des Sets.

Ein **neues, ungeöffnetes** Set enthält seine Figuren noch. Ein
gebrauchtes in aller Regel nicht mehr: Wer ein Set mit Figuren kauft,
trägt die Figuren einzeln ein – steht eine Figur also nicht in der
Sammlung, hat er sie auch nicht.

Der Live-Scanner kann beides nur unterscheiden, wenn der Zustand
mitkommt. Angehängt als **viertes** Feld, damit ältere Leser, die nur drei
lesen, genau das bekommen, was sie bisher bekamen.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "si.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('sven', 'x', 1, ?)", (now,)).lastrowid
        for nr, zustand in (("7931-1", "new"), ("75192-1", "used")):
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity,"
                " condition, added_at) VALUES (?, 'set', ?, 1, ?, ?)",
                (nr, "Set " + nr, zustand, now))
            conn.execute(
                "INSERT INTO set_contents (set_no, fig_no, qty)"
                " VALUES (?, 'sw0309', 1)", (nr,))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def _in_sets(client):
    d = client.post("/api/suggest_info", json={"items": [
        {"item_id": "sw0309", "item_type": "minifig"}]}).json()
    return d["sw0309"].get("in_sets", "")


def test_der_zustand_steht_als_viertes_feld(client):
    roh = _in_sets(client)
    assert roh, "in_sets fehlt ganz"
    stuecke = dict()
    for teil in roh.split(";;"):
        felder = teil.split("|")
        assert len(felder) == 4, felder
        stuecke[felder[0]] = felder[3]
    assert stuecke["7931-1"] == "new"
    assert stuecke["75192-1"] == "used"


def test_die_ersten_drei_felder_bleiben_wie_sie_waren(client):
    """Ein älterer Leser nimmt Nummer, Name und Anzahl – und soll genau
    die weiterhin bekommen."""
    for teil in _in_sets(client).split(";;"):
        nummer, name, anzahl = teil.split("|")[:3]
        assert nummer in ("7931-1", "75192-1")
        assert name == "Set " + nummer
        assert anzahl == "1"
