"""Abgleich für externen Zugriff mit eigener Datenbank (backend/sync.py).

Die Gegenstelle gleicht ihre eigene Datenbank mit der Instanz ab: holen, was
sich seit ihrem letzten Stand geändert hat, schicken, was bei ihr geändert
wurde. Diese Tests beschreiben die Regeln, nach denen das geht.

Vor allem geprüft wird, was dabei schiefgehen kann, ohne dass es jemand
merkt: ein Schreibweg der Web-App, der den Stand nicht hochzählt (dann
erfährt das Gerät nie davon), eine Löschung ohne Vermerk (dann kommt der
Eintrag beim nächsten Abgleich zurück), ein Kaufpreis, der an einen
Standard-Benutzer geht.
"""
import time

import pytest
from fastapi.testclient import TestClient

import core
import main
import sync

FIGUR = {"item_id": "sw0001a", "item_type": "minifig", "name": "Battle Droid",
         "quantity": 2, "condition": "used"}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "sync.db"))
    core.init_db()
    with core.db() as conn:
        for n, (name, dealer) in enumerate((("profi", 1), ("standard", 0)), start=1):
            conn.execute("INSERT INTO users (id, username, password_hash, is_admin, "
                         "is_dealer, created_at) VALUES (?, ?, 'x', ?, ?, ?)",
                         (n, name, 1 if dealer else 0, dealer, int(time.time())))


def _client(nr, name, admin):
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(nr, name, admin)
    return c


@pytest.fixture
def profi(db):
    return _client(1, "profi", True)


@pytest.fixture
def standard(db):
    return _client(2, "standard", False)


def _pull(c, since=0, **kw):
    r = c.get("/api/sync/pull", params={"since": since, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _saetze(c, since=0, table=None):
    return [s for s in _pull(c, since)["changes"] if table is None or s["table"] == table]


def _push(c, *changes):
    r = c.post("/api/sync/push", json={"changes": list(changes)})
    assert r.status_code == 200, r.text
    return r.json()


def _eintrag(c, **extra):
    c.post("/api/collection", json={**FIGUR, **extra})
    return c.get("/api/collection").json()["items"][0]


def _stand(c):
    return c.get("/api/sync/info").json()["rev"]


# ------------------------------------------------------------ Grundlagen

def test_bestand_bekommt_uuid_und_stand(profi):
    """Was schon vor dem Update da war, bekommt bei der Wanderung eine UUID
    und einen Stand – sonst sähe ein Gerät die alte Sammlung nie."""
    _eintrag(profi)
    with core.db() as conn:
        conn.execute("UPDATE collection SET uuid = NULL, rev = NULL")
    core.init_db()
    s = _saetze(profi, table="collection")
    assert len(s) == 1 and len(s[0]["uuid"]) == 36 and s[0]["rev"] > 0


def test_jeder_schreibweg_zaehlt_hoch(profi):
    """Stichprobe über die Endpunkte der Web-App, nicht über SQL: Jeder
    Weg muss den Stand hochzählen, sonst erfährt das Gerät nichts davon."""
    e = _eintrag(profi)
    wege = [
        lambda: profi.patch(f"/api/collection/{e['id']}", json={"quantity": 5}),
        lambda: profi.post(f"/api/collection/{e['id']}/purchases",
                           json={"quantity": 1, "price": 3.5, "source": "Börse"}),
        lambda: profi.post("/api/wanted", json={"item_id": "sw0002", "item_type": "minifig",
                                                "name": "Boba"}),
        lambda: profi.post("/api/lists", json={"name": "Flohmarkt"}),
        lambda: profi.post("/api/import/csv", json={"csv": "Nummer;Anzahl\nsw0003;1"}),
    ]
    for weg in wege:
        vorher = _stand(profi)
        assert weg().status_code == 200
        assert _stand(profi) > vorher


def test_stand_steigt_ueber_tabellen_hinweg_streng(profi):
    _eintrag(profi)
    profi.post("/api/wanted", json={"item_id": "sw0002", "item_type": "minifig", "name": "B"})
    revs = [s["rev"] for s in _saetze(profi)]
    assert revs == sorted(revs) and len(set(revs)) == len(revs)


def test_pull_in_seiten(profi):
    for i in range(5):
        profi.post("/api/wanted", json={"item_id": f"sw{i}", "item_type": "minifig", "name": "x"})
    erste = _pull(profi, limit=2)
    assert erste["more"] and len(erste["changes"]) == 2
    zweite = _pull(profi, since=erste["rev"], limit=10)
    assert not zweite["more"]
    uuids = [s["uuid"] for s in erste["changes"] + zweite["changes"]]
    assert len(uuids) == len(set(uuids)) == 5


def test_verweise_und_benutzer_werden_uebersetzt(profi):
    e = _eintrag(profi, paid_price=4.0, paid_source="manual")
    kauf = _saetze(profi, table="purchases")[0]
    eintrag = _saetze(profi, table="collection")[0]
    assert kauf["fields"]["entry_uuid"] == eintrag["uuid"]
    assert "entry_id" not in kauf["fields"] and "id" not in eintrag["fields"]
    assert eintrag["fields"]["added_by"] == "profi"
    assert e["id"]


# ------------------------------------------------------------ Löschen

def test_loeschen_in_der_web_app_hinterlaesst_vermerk(profi):
    """Ohne Vermerk käme der Eintrag beim nächsten Abgleich vom Gerät
    einfach wieder – mitsamt Kaufbuch."""
    e = _eintrag(profi, paid_price=4.0, paid_source="manual")
    stand = _stand(profi)
    profi.delete(f"/api/collection/{e['id']}")
    weg = _saetze(profi, since=stand)
    assert {s["table"] for s in weg} == {"collection", "purchases"}
    assert all(s.get("deleted") for s in weg)


def test_wiederhergestellt_ist_nicht_geloescht(profi):
    """Das Zurückspielen einer Sicherung löscht erst alles und fügt dann neu
    ein. Die Vermerke der gelöschten Zeilen dürfen nicht stehen bleiben –
    und die Geräte beginnen in einem neuen Zeitalter von vorn."""
    _eintrag(profi)
    vorher = profi.get("/api/sync/info").json()["epoch"]
    sicherung = profi.get("/api/backup").json()
    assert profi.post("/api/restore", json=sicherung).status_code == 200
    assert profi.get("/api/sync/info").json()["epoch"] != vorher
    alle = _saetze(profi)
    lebend = {s["uuid"] for s in alle if not s.get("deleted")}
    geloescht = {s["uuid"] for s in alle if s.get("deleted")}
    assert lebend and not (lebend & geloescht)


# ------------------------------------------------------------ Push

def test_neu_vom_geraet(profi):
    r = _push(profi, {"table": "collection", "uuid": "g-1", "updated_at": 1_700_000_000_000,
                      "fields": {**FIGUR, "added_at": 1_700_000_000, "added_by": "profi",
                                 "notes": "vom Handy"}})
    assert r["rejected"] == [] and r["accepted"][0]["uuid"] == "g-1"
    item = profi.get("/api/collection").json()["items"][0]
    assert item["notes"] == "vom Handy" and item["quantity"] == 2
    # Die Zeit des Geräts bleibt – sie entscheidet später über Konflikte.
    assert _saetze(profi, table="collection")[0]["updated_at"] == 1_700_000_000_000


def test_konflikt_neuer_gewinnt_gleichstand_instanz(profi):
    _eintrag(profi)
    s = _saetze(profi, table="collection")[0]
    alt = s["rev"]
    # Jemand ändert in der Web-App – danach schickt das Gerät auf altem Stand.
    profi.patch(f"/api/collection/{profi.get('/api/collection').json()['items'][0]['id']}",
                json={"notes": "Web"})
    aktuell = _saetze(profi, table="collection")[0]
    aelter = {"table": "collection", "uuid": s["uuid"], "updated_at": aktuell["updated_at"],
              "base_rev": alt, "fields": {"notes": "Handy"}}
    r = _push(profi, aelter)
    assert r["rejected"][0]["reason"] == "conflict"
    assert r["rejected"][0]["server"]["fields"]["notes"] == "Web"
    neuer = {**aelter, "updated_at": aktuell["updated_at"] + 1}
    assert _push(profi, neuer)["rejected"] == []


def test_gleiche_uuid_wird_nie_ueberschrieben(profi):
    """Zwei Geräte, dieselbe Figur, dieselbe UUID (die Gegenstelle leitet sie aus
    dem Artikel ab). Überschriebe die Instanz, wäre eine Figur weg."""
    _push(profi, {"table": "wanted", "uuid": "gleich", "updated_at": 1,
                  "fields": {"item_id": "sw9", "item_type": "minifig", "name": "a", "added_at": 1}})
    r = _push(profi, {"table": "wanted", "uuid": "gleich", "updated_at": 2, "base_rev": None,
                      "fields": {"item_id": "sw9", "item_type": "minifig", "name": "b", "added_at": 1}})
    assert r["rejected"][0]["reason"] == "conflict"
    assert r["rejected"][0]["server"]["fields"]["name"] == "a"


def test_doppelter_artikel_mit_anderer_uuid(profi):
    _eintrag(profi)
    r = _push(profi, {"table": "collection", "uuid": "anders", "updated_at": 1,
                      "fields": {**FIGUR, "added_at": 1}})
    assert r["rejected"][0]["reason"] == "duplicate"
    assert r["rejected"][0]["server"]["fields"]["item_id"] == "sw0001a"


def test_verwaister_kaufposten(profi):
    r = _push(profi, {"table": "purchases", "uuid": "k", "updated_at": 1,
                      "fields": {"entry_uuid": "gibts-nicht", "quantity": 1, "created_at": 1}})
    assert r["rejected"][0]["reason"] == "orphan"


@pytest.mark.parametrize("feld, wert", [("price_used", "1e999"), ("price_used", "-1"),
                                        ("condition", '"kaputt"'), ("quantity", "0")])
def test_ungueltiges_wird_abgewiesen(profi, feld, wert):
    """`1e999` als Preis legte die Web-App lahm (2.90.21) – über den Sync
    darf es genauso wenig herein. Roh geschickt: Pythons JSON liest
    `1e999` als unendlich, kann es aber selbst nicht schreiben."""
    import json
    felder = json.dumps({**FIGUR, "added_at": 1})[:-1] + f', "{feld}": {wert}}}'
    roh = ('{"changes": [{"table": "collection", "uuid": "x", "updated_at": 1, "fields": '
           + felder + '}]}')
    r = profi.post("/api/sync/push", content=roh, headers={"Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["rejected"][0]["reason"] == "invalid"
    assert profi.get("/api/collection").json()["items"] == []


def test_ein_fehler_haelt_die_anderen_nicht_auf(profi):
    r = _push(profi,
              {"table": "collection", "uuid": "a", "updated_at": 1,
               "fields": {**FIGUR, "added_at": 1, "condition": "kaputt"}},
              {"table": "wanted", "uuid": "b", "updated_at": 1,
               "fields": {"item_id": "sw2", "item_type": "minifig", "name": "x", "added_at": 1}})
    assert [a["uuid"] for a in r["accepted"]] == ["b"]


def test_uhr_aus_der_zukunft_wird_gekuerzt(profi):
    """Ein Gerät, dessen Uhr ein Jahr vorgeht, gewönne sonst jeden Konflikt."""
    zukunft = int(time.time() * 1000) + 365 * 86_400_000
    _push(profi, {"table": "wanted", "uuid": "z", "updated_at": zukunft,
                  "fields": {"item_id": "sw2", "item_type": "minifig", "name": "x", "added_at": 1}})
    s = _saetze(profi, table="wanted")[0]
    assert s["updated_at"] <= int(time.time() * 1000) + sync.ZUKUNFT_MS


def test_geloescht_vom_geraet_samt_kaufbuch(profi):
    _eintrag(profi, paid_price=4.0, paid_source="manual")
    s = _saetze(profi, table="collection")[0]
    r = _push(profi, {"table": "collection", "uuid": s["uuid"], "updated_at": s["updated_at"] + 1,
                      "base_rev": s["rev"], "deleted": True})
    assert r["rejected"] == []
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0] == 0


def test_kaufposten_zieht_die_summe_nach(profi):
    _eintrag(profi)
    e = _saetze(profi, table="collection")[0]
    _push(profi, {"table": "purchases", "uuid": "k1", "updated_at": 1,
                  "fields": {"entry_uuid": e["uuid"], "quantity": 2, "unit_price": 1.25,
                             "source": "Börse", "created_at": 1}})
    assert profi.get("/api/collection").json()["items"][0]["paid_price"] == 2.5


# ------------------------------------------------------------ Rechte

def test_standard_bekommt_keine_kaufpreise_und_kein_kaufbuch(profi, standard):
    _eintrag(profi, paid_price=4.0, paid_source="manual")
    s = _pull(standard)
    assert not s["dealer"]
    assert {x["table"] for x in s["changes"]} == {"collection", "price_history"} \
        or {x["table"] for x in s["changes"]} == {"collection"}
    felder = [x for x in s["changes"] if x["table"] == "collection"][0]["fields"]
    # Weggelassen, nicht auf null gesetzt: „fehlt“ heißt „nicht für dich“.
    assert "paid_price" not in felder and "paid_source" not in felder


def test_standard_kaufpreise_werden_ignoriert_kaufbuch_verboten(profi, standard):
    _eintrag(profi, paid_price=4.0, paid_source="manual")
    e = _saetze(profi, table="collection")[0]
    r = _push(standard, {"table": "collection", "uuid": e["uuid"], "updated_at": e["updated_at"] + 1,
                         "base_rev": e["rev"], "fields": {"paid_price": 0.01, "notes": "neu"}})
    assert r["rejected"] == []
    item = profi.get("/api/collection").json()["items"][0]
    assert item["paid_price"] == 4.0 and item["notes"] == "neu"
    r = _push(standard, {"table": "purchases", "uuid": "k", "updated_at": 1,
                         "fields": {"entry_uuid": e["uuid"], "quantity": 1, "created_at": 1}})
    assert r["rejected"][0]["reason"] == "forbidden"


def test_standard_darf_listen_nur_verbuchen(profi, standard):
    lid = profi.post("/api/lists", json={"name": "Börse"}).json()["id"]
    profi.post(f"/api/lists/{lid}/items", json={"item_id": "sw1", "name": "x", "paid_price": 3})
    liste = _saetze(profi, table="shopping_lists")[0]
    posten = _saetze(profi, table="shopping_items")[0]
    assert "paid_price" not in _saetze(standard, table="shopping_items")[0]["fields"]
    r = _push(standard, {"table": "shopping_lists", "uuid": liste["uuid"], "updated_at": 9**12,
                         "base_rev": liste["rev"], "fields": {"name": "meins"}})
    assert r["rejected"][0]["reason"] == "forbidden"
    r = _push(standard, {"table": "shopping_items", "uuid": posten["uuid"],
                         "updated_at": posten["updated_at"] + 1, "base_rev": posten["rev"],
                         "fields": {"done": 1, "done_by": "standard", "done_at": 5}})
    assert r["rejected"] == []
    r = _push(standard, {"table": "shopping_items", "uuid": posten["uuid"],
                         "updated_at": posten["updated_at"] + 2, "base_rev": r["accepted"][0]["rev"],
                         "fields": {"paid_price": 0}})
    assert r["rejected"][0]["reason"] == "forbidden"


def test_archiv_verschwindet_fuer_standard_und_kommt_zurueck(profi, standard):
    """Das Archiv ist nur für Profis. Für Standard-Benutzer erscheint eine
    archivierte Liste samt Artikeln als gelöscht – und holt ein Profi sie
    zurück, müssen auch die Artikel wiederkommen."""
    lid = profi.post("/api/lists", json={"name": "Börse"}).json()["id"]
    profi.post(f"/api/lists/{lid}/items", json={"item_id": "sw1", "name": "x"})
    stand = _pull(standard)["rev"]
    profi.post(f"/api/lists/{lid}/archive", json={"archived": True})
    danach = _saetze(standard, since=stand)
    assert {s["table"] for s in danach} == {"shopping_lists", "shopping_items"}
    assert all(s.get("deleted") for s in danach)
    stand = _pull(standard)["rev"]
    profi.post(f"/api/lists/{lid}/archive", json={"archived": False})
    zurueck = _saetze(standard, since=stand)
    assert {s["table"] for s in zurueck} == {"shopping_lists", "shopping_items"}
    assert not any(s.get("deleted") for s in zurueck)


def test_ohne_anmeldung_nichts(db):
    c = TestClient(main.app)
    assert c.get("/api/sync/pull").status_code == 401
    assert c.post("/api/sync/push", json={"changes": []}).status_code == 401


def test_eintrag_samt_kaufposten_loeschen_kommt_durch(profi):
    """Der Vorfall aus dem ersten Lauf gegen eine echte Instanz: Das Gerät
    schickte die Löschung des Kaufpostens vor der des Eintrags. Der Posten
    zog die Summe nach, der Eintrag bekam die Uhrzeit der Instanz, seine
    Löschung galt als älter und wurde abgewiesen – der Eintrag kam zurück."""
    _eintrag(profi, paid_price=4.0, paid_source="manual")
    e = _saetze(profi, table="collection")[0]
    k = _saetze(profi, table="purchases")[0]
    geloescht = e["updated_at"] + 1
    r = _push(profi,
              {"table": "purchases", "uuid": k["uuid"], "updated_at": geloescht,
               "base_rev": k["rev"], "deleted": True},
              {"table": "collection", "uuid": e["uuid"], "updated_at": geloescht,
               "base_rev": e["rev"], "deleted": True})
    assert r["rejected"] == []
    assert profi.get("/api/collection").json()["items"] == []
    # Und in der anderen Reihenfolge – Eltern zuerst, wie es die Gegenstelle jetzt tut.
    _eintrag(profi, paid_price=4.0, paid_source="manual")
    e = _saetze(profi, table="collection")[-1]
    k = [s for s in _saetze(profi, table="purchases") if not s.get("deleted")][0]
    r = _push(profi,
              {"table": "collection", "uuid": e["uuid"], "updated_at": geloescht + 10,
               "base_rev": e["rev"], "deleted": True},
              {"table": "purchases", "uuid": k["uuid"], "updated_at": geloescht + 10,
               "base_rev": k["rev"], "deleted": True})
    assert r["rejected"] == []


def test_tagesstand_zurueckspielen_beginnt_neues_zeitalter(profi):
    """Ein Tagesstand ersetzt die ganze Datei – samt altem Zählerstand. Ein
    Gerät, das schon weiter war, hielte sich sonst für aktuell und sähe
    nichts, bis der Zähler wieder aufgeholt hat."""
    import os
    import sqlite3
    _eintrag(profi)
    bdir = os.path.join(os.path.dirname(core.DB_PATH), "backups")
    os.makedirs(bdir, exist_ok=True)
    name = "brickfolio-2026-09-01.db"
    live = sqlite3.connect(core.DB_PATH)
    ziel = sqlite3.connect(os.path.join(bdir, name))
    live.backup(ziel)
    ziel.close()
    live.close()
    vorher = profi.get("/api/sync/info").json()["epoch"]
    r = profi.post("/api/backup_restore_file", json={"name": name})
    assert r.status_code == 200, r.text
    assert profi.get("/api/sync/info").json()["epoch"] != vorher
