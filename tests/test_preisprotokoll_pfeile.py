"""Das Preis-Protokoll sagt, wohin der Preis ging.

Eine Zahl allein sagt nicht, ob sie gut ist: „Ø 4,55 €" liest sich gleich,
ob der Preis gestiegen oder gefallen ist. Der Endpunkt liefert deshalb zu
jedem Punkt den **vorherigen** Wert desselben Artikels mit; die Oberfläche
macht daraus einen grünen Pfeil hoch oder einen roten runter.

Der Fallstrick steckt im `LIMIT`: Das Protokoll zeigt die jüngsten 50
Zeilen, aber der vorherige Punkt eines Artikels liegt fast immer weiter
zurück. Das Fenster muss deshalb über den **ganzen** Verlauf laufen und
erst danach begrenzt werden.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "pl.db"))
    core.init_db()
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('anna', 'x', 1, 1, ?)", (int(time.time()),))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    return c


def punkte(*werte, item="sw0001", typ="minifig", start=1_000_000):
    """Einen Preisverlauf anlegen: (ts-Versatz, neu, gebraucht)."""
    with core.db() as conn:
        for i, (neu, gebr) in enumerate(werte):
            conn.execute(
                "INSERT INTO price_history (item_id, item_type, ts,"
                " price_new, price_used, source) VALUES (?, ?, ?, ?, ?, 'auto')",
                (item, typ, start + i * 3600, neu, gebr))


def test_der_vorherige_wert_kommt_mit(client):
    punkte((4.00, 2.00), (5.00, 1.50))
    e = client.get("/api/price_log").json()["entries"]
    jung = e[0]                       # jüngster zuerst
    assert jung["price_new"] == 5.00
    assert jung["vorher_new"] == 4.00, "gestiegen – muss erkennbar sein"
    assert jung["vorher_used"] == 2.00, "gefallen – muss erkennbar sein"


def test_der_erste_punkt_hat_keinen_vorgaenger(client):
    punkte((4.00, 2.00))
    e = client.get("/api/price_log").json()["entries"]
    assert e[0]["vorher_new"] is None, "ohne Vorgänger darf kein Pfeil kommen"


def test_jeder_artikel_zaehlt_fuer_sich(client):
    """Sonst stünde neben einer Figur der Vorgänger eines Sets."""
    punkte((4.00, 2.00), (5.00, 2.00), item="sw0001")
    punkte((100.0, 80.0), item="75192-1", typ="set", start=2_000_000)
    # Die Liste kommt absteigend – je Nummer also den **ersten** nehmen,
    # nicht den letzten. (Genau daran ist dieser Test beim Schreiben
    # zuerst gescheitert: Ein Dictionary behält den letzten Treffer, und
    # das war der älteste Punkt, der naturgemäß keinen Vorgänger hat.)
    e = {}
    for x in client.get("/api/price_log").json()["entries"]:
        e.setdefault(x["item_id"], x)
    assert e["75192-1"]["vorher_new"] is None
    assert e["sw0001"]["vorher_new"] == 4.00


def test_der_vorgaenger_darf_ausserhalb_der_anzeige_liegen(client):
    """Der eigentliche Fallstrick: 60 fremde Punkte drängen den eigenen
    Vorgänger aus den angezeigten Zeilen – gefunden werden muss er
    trotzdem."""
    punkte((4.00, 2.00), item="sw0001", start=1_000_000)
    for i in range(60):
        punkte((9.0, 9.0), item="sw%04d" % (100 + i), start=1_100_000 + i * 60)
    punkte((7.00, 2.00), item="sw0001", start=1_900_000)
    e = client.get("/api/price_log?limit=50").json()["entries"]
    jung = next(x for x in e if x["item_id"] == "sw0001")
    assert jung["price_new"] == 7.00
    assert jung["vorher_new"] == 4.00, \
        "das Fenster lief über die angezeigten Zeilen statt über den Verlauf"


def test_die_oberflaeche_vergleicht_auf_cent():
    """4,3760 und 4,3820 stehen beide als „4,38 €" da – ein Pfeil daneben
    behauptete eine Bewegung, die in der Zeile nicht zu sehen ist."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js") \
        .read_text(encoding="utf-8")
    i = js.index("function preisPfeil(")
    block = js[i:js.index("async function loadPriceLog(", i)]
    assert "Math.round(Number(vorher) * 100)" in block
    assert "if (a === b) return \"\";" in block, "unverändert = kein Pfeil"
    assert "pl-up" in block and "pl-down" in block
