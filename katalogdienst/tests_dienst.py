"""Was der Katalogdienst zusichert.

Die beiden Läufe selbst sind aus der App übernommen und dort über Tage an
echten Daten gereift – ihre Tests stehen im Hauptrepo. Hier geht es um das,
was neu ist: die Schnittstelle, die die Konsole bedient, und die Trennung
der beiden Token.
"""
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "steuern")
    monkeypatch.setenv("LESE_TOKEN", "lesen")
    import katalog
    monkeypatch.setattr(katalog, "DB_PATH", str(tmp_path / "k.db"))
    katalog.init_db()
    import dienst
    c = TestClient(dienst.app)
    c.headers["Authorization"] = "Bearer steuern"
    return c


def _zeile(item_no="cas001", merkmale="", stand=100):
    import katalog
    with katalog.db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO katalog_index (item_no, item_type, name,"
            " such, img_url, merkmale, updated_at) VALUES (?, 'minifig',"
            " 'Dragon Master', 'dragonmaster', 'u', ?, ?)",
            (item_no, merkmale, stand))


def test_ohne_token_geht_nichts(client):
    """Ein offener Katalogdienst im Heimnetz könnte fremdes Kontingent
    verbrennen – BrickLink lässt 5.000 Abrufe am Tag zu, und dasselbe
    Kontingent trägt die Preisabfragen der Instanzen."""
    c = TestClient(client.app)
    assert c.get("/api/status").status_code == 401
    assert c.post("/api/abzug/start").status_code == 401
    # Der Lebenszeichen-Endpunkt bleibt offen, sonst ließe sich von außen
    # nicht prüfen, ob der Dienst überhaupt läuft.
    assert c.get("/api/health").status_code == 200


def test_der_lesetoken_darf_nicht_steuern(client):
    """Eine Instanz soll den Abzug beziehen können, ohne ihn zu steuern."""
    c = TestClient(client.app)
    c.headers["Authorization"] = "Bearer lesen"
    assert c.get("/api/status").status_code == 401
    assert c.post("/api/abzug/start").status_code == 401
    assert c.get("/api/index?token=lesen").status_code == 200


def test_der_admintoken_darf_auch_lesen(client):
    _zeile()
    assert client.get("/api/index?token=steuern").status_code == 401, \
        "der Admin-Token gilt hier nicht – es ist ein eigener Kanal"
    assert client.get("/api/index?token=lesen").json()["gesamt"] == 1


def test_der_stand_zaehlt_frisch_statt_aus_dem_speicher(client):
    """Als Feld im Laufzustand stand `offen` nach jedem Neustart auf 0, und
    die Oberfläche meldete „alle Bilder angesehen", während in Wahrheit
    8.328 Figuren offen waren (gesehen am 22.08.2026)."""
    _zeile("cas001", merkmale="")
    _zeile("cas002", merkmale="torso red")
    z = client.get("/api/status").json()["zeilen"]
    assert z == {"gesamt": 2, "offen": 1, "beschrieben": 1}


def test_themen_dazu_und_ruhen_lassen(client):
    assert client.post("/api/themen", json={"praefix": "wtf"}).json()["ok"]
    themen = {t["praefix"]: t for t in client.get("/api/status").json()["themen"]}
    assert themen["wtf"]["aktiv"] == 1
    client.delete("/api/themen/wtf")
    themen = {t["praefix"]: t for t in client.get("/api/status").json()["themen"]}
    assert themen["wtf"]["aktiv"] == 0


def test_nur_buchstaben_als_praefix(client):
    """Das Präfix wandert in eine Adresse – „../" hätte dort nichts zu
    suchen. Zu lange Werte weist schon Pydantic ab (422), der Rest der
    Prüfung liegt im Endpunkt (400); beides ist eine Ablehnung."""
    for unsinn in ("x", "../etc", "sw1", "viel-zu-lang"):
        code = client.post("/api/themen", json={"praefix": unsinn}).status_code
        assert code >= 400, "%s wurde angenommen" % unsinn


def test_ohne_bricklink_kein_abzug(client):
    """Statt in einen 401-Regen zu laufen und ihn für Lücken zu halten."""
    r = client.post("/api/abzug/start")
    assert r.status_code == 400 and "BrickLink" in r.json()["detail"]


def test_die_seite_endet_am_letzten_zeitstempel(client):
    """`stand` ist der Zeitstempel der letzten gelieferten Zeile, nicht die
    Uhrzeit: Sonst übersähe der nächste Abruf alles, was zwischen Abfrage
    und Antwort geschrieben wurde."""
    _zeile("a001", stand=100)
    _zeile("a002", stand=200)
    d = client.get("/api/index?token=lesen&limit=1").json()
    assert d["stand"] == 100 and d["mehr"] is True
    d2 = client.get("/api/index?token=lesen&limit=1&seit=100").json()
    assert [z["item_no"] for z in d2["zeilen"]] == ["a002"]


def test_eine_leere_seite_haelt_den_stand(client):
    """Sonst fiele der Wasserstand der Instanz auf 0 zurück und sie zöge
    beim nächsten Mal den ganzen Abzug erneut."""
    d = client.get("/api/index?token=lesen&seit=500").json()
    assert d["zeilen"] == [] and d["stand"] == 500 and d["mehr"] is False
