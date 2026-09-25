"""Profile und Entdecken im Tausch-Netzwerk.

Der Hub ist hier eine Attrappe: Was er liefert, steht im Test; geprüft wird,
was die Instanz daraus macht – und dass die eigene Wunschliste die Instanz
nur verlässt, wenn „Wunschliste zeigen" gesetzt ist.
"""
import time

import pytest

import core
import hub
import main
from fastapi.testclient import TestClient


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "c.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) "
            "VALUES ('anna', 'x', 1, ?)", (int(time.time()),)).lastrowid
    core.set_setting("hub_token", "bft_test")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    gesendet = {"wants": [], "profile": []}
    monkeypatch.setattr(hub, "put_wants",
                        lambda l: gesendet["wants"].append(l) or {"count": len(l)})

    def put_profile(d):
        gesendet["profile"].append(d)
        return {**d, "member_id": "mem_ich", "stats": {"offers": 0, "trades": 0}}
    monkeypatch.setattr(hub, "put_profile", put_profile)
    c.gesendet = gesendet
    return c


def wunsch(nr, name="Figur"):
    with core.db() as conn:
        conn.execute("INSERT INTO wanted (item_id, item_type, name, added_at) "
                     "VALUES (?, 'minifig', ?, ?)", (nr, name, int(time.time())))


def sammlung(nr, menge, name="Figur"):
    with core.db() as conn:
        conn.execute("INSERT INTO collection (item_id, item_type, name, quantity, "
                     "condition, added_at) VALUES (?, 'minifig', ?, ?, 'used', ?)",
                     (nr, name, menge, int(time.time())))


def test_entdecken_findet_beide_richtungen(api, monkeypatch):
    wunsch("sw0036")
    sammlung("sw0188", 3)                 # 2 davon abgebbar
    sammlung("sw0001", 1)                 # nichts abgebbar
    monkeypatch.setattr(hub, "offers", lambda p=None: [
        {"member_id": "mem_b", "display_name": "Bruno", "item_id": "sw0036",
         "item_type": "minifig", "name": "Trooper"},
        {"member_id": "mem_b", "display_name": "Bruno", "item_id": "sw9999",
         "item_type": "minifig", "name": "Andere"}])
    monkeypatch.setattr(hub, "wants", lambda: [
        {"member_id": "mem_c", "display_name": "Carla", "item_id": "sw0188",
         "item_type": "minifig", "name": "Dotted"},
        {"member_id": "mem_c", "display_name": "Carla", "item_id": "sw0001",
         "item_type": "minifig", "name": "Nur einmal da"}])
    monkeypatch.setattr(hub, "profiles", lambda: [
        {"member_id": "mem_ich", "eigen": True, "themes": ["Star Wars", "City"]},
        {"member_id": "mem_b", "display_name": "Bruno", "themes": ["star wars"],
         "offers": 2},
        {"member_id": "mem_c", "display_name": "Carla", "themes": ["Ninjago"]}])
    d = api.get("/api/hub/entdecken").json()
    assert [h["item_id"] for h in d["hat"]] == ["sw0036"]
    assert [(s["item_id"], s["hier_abgebbar"]) for s in d["sucht"]] == [("sw0188", 2)]
    assert [p["member_id"] for p in d["passt"]] == ["mem_b"], \
        "gleiches Thema, Groß-/Kleinschreibung egal"
    assert api.gesendet["wants"] == [], \
        "ohne „Wunschliste zeigen“ verlässt sie die Instanz nicht"


def test_wunschliste_geht_erst_nach_dem_einschalten_raus(api, monkeypatch):
    wunsch("sw0036", "Trooper")
    r = api.put("/api/hub/profil", json={"about": "Hallo", "themes": [" Star Wars "],
                                         "wants_public": True})
    assert r.status_code == 200
    assert api.gesendet["profile"][-1]["themes"] == ["Star Wars"]
    assert [w["item_id"] for w in api.gesendet["wants"][-1]] == ["sw0036"]
    # Unverändert: kein zweites Senden
    main.community.wuensche_nachziehen()
    assert len(api.gesendet["wants"]) == 1
    # Neuer Wunsch: wird nachgezogen
    wunsch("sw0188", "Dotted")
    main.community.wuensche_nachziehen()
    assert {w["item_id"] for w in api.gesendet["wants"][-1]} == {"sw0036", "sw0188"}


def test_sammlungsgroesse_nur_wenn_gezeigt(api):
    sammlung("sw0001", 3)
    api.put("/api/hub/profil", json={"show_collection": False})
    assert "collection_count" not in api.gesendet["profile"][-1]
    api.put("/api/hub/profil", json={"show_collection": True})
    assert api.gesendet["profile"][-1]["collection_count"] == 3


def test_alter_hub_gibt_einen_verstaendlichen_hinweis(api, monkeypatch):
    def alt(*a, **k):
        raise hub.HubError(404, "unbekannter Endpunkt")
    monkeypatch.setattr(hub, "profile", alt)
    r = api.get("/api/hub/profil")
    assert r.status_code == 501 and "aktualisiert" in r.json()["detail"]


def test_fremdes_profil_zeigt_was_passt(api, monkeypatch):
    wunsch("sw0036")
    sammlung("sw0188", 2)
    monkeypatch.setattr(hub, "profile", lambda mid="": {
        "member_id": mid, "display_name": "Carla",
        "offers": [{"item_id": "sw0036", "item_type": "minifig", "name": "T"}],
        "wants": [{"item_id": "sw0188", "item_type": "minifig", "name": "D"}]})
    p = api.get("/api/hub/profil/mem_c").json()
    assert p["offers"][0]["auf_wunschliste"] is True
    assert p["wants"][0]["hier_abgebbar"] == 1


def test_ohne_verbindung_kein_entdecken(api):
    core.set_setting("hub_token", "")
    assert api.get("/api/hub/entdecken").status_code == 400


def test_trennen_zieht_eine_gezeigte_wunschliste_zurueck(api, monkeypatch):
    core.set_setting("hub_wuensche_zeigen", "1")
    monkeypatch.setattr(hub, "profile", lambda mid="": {
        "about": "x", "themes": ["City"], "wants_public": True})
    api.post("/api/hub/disconnect")
    assert api.gesendet["profile"][-1]["wants_public"] is False
    assert core.get_setting("hub_wuensche_zeigen") in ("", None)
