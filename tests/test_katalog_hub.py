"""Warum der Abzug einmal zentral liegt statt viermal lokal.

Jede Instanz baute ihn bisher selbst: Nummern der Reihe nach bei BrickLink
abklappern (Tage, eigenes Kontingent) und danach jedes Bild von einem
Sehmodell beschreiben lassen (rund 24 Stunden Grafikeinheit für 9.741
Figuren). Dieselbe Arbeit für dasselbe Ergebnis – der Katalog beschreibt
BrickLinks Fotos, nicht die Sammlung von irgendwem. Nerdfan, Paul und Kello
hatten deshalb null Zeilen im Abzug, und seit dem 23.08. auch kein Sehmodell
mehr, mit dem sie ihn erarbeiten könnten.

Diese Instanz ist die Quelle und schiebt ihren Stand hoch. Nur sie: Ohne
`katalog_token` bleibt der Schieber still, und der Hub weist Schreibversuche
ohne `can_katalog` ohnehin ab.
"""
import pytest

import core
import hub
import integrations
import main


@pytest.fixture
def abzug(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "hub.db"))
    core.init_db()
    with core.db() as conn:
        for nr, merkmale, stand in (("sw0010", "head tan smooth", 100),
                                    ("sw0021", "torso white tunic", 200),
                                    ("sw0099", "", 150)):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such, "
                "img_url, farben, art, merkmale, updated_at) VALUES "
                "(?, 'minifig', ?, ?, '', 'tan', 'droid', ?, ?)",
                (nr, nr, nr, merkmale, stand))
    monkeypatch.setattr(integrations, "ollama_enabled", lambda: True)
    monkeypatch.setattr(integrations, "ollama_bild_modell",
                        lambda: "qwen3-vl:latest")
    return True


def test_ohne_token_bleibt_er_still(abzug, monkeypatch):
    """Nur eine Instanz im Netz ist die Quelle – die anderen schweigen."""
    gerufen = []
    monkeypatch.setattr(hub, "katalog_hochladen",
                        lambda z: gerufen.append(z) or {"geschrieben": len(z)})
    erg = main._katalog_zum_hub()
    assert erg["geschrieben"] == 0 and not gerufen


def test_erster_lauf_schiebt_alles(abzug, monkeypatch):
    core.set_setting("katalog_token", "geheim")
    gesehen = {}
    monkeypatch.setattr(hub, "katalog_hochladen",
                        lambda z: gesehen.update(zeilen=z) or
                        {"geschrieben": len(z)})
    erg = main._katalog_zum_hub()
    assert erg["geschrieben"] == 3
    assert {z["item_no"] for z in gesehen["zeilen"]} == {"sw0010", "sw0021",
                                                         "sw0099"}


def test_zweiter_lauf_schiebt_nichts_mehr(abzug, monkeypatch):
    """Sonst gingen bei jedem Lauf 9.741 Zeilen über die Leitung."""
    core.set_setting("katalog_token", "geheim")
    monkeypatch.setattr(hub, "katalog_hochladen",
                        lambda z: {"geschrieben": len(z)})
    main._katalog_zum_hub()
    assert main._katalog_zum_hub()["geschrieben"] == 0


def test_das_modell_faehrt_mit(abzug, monkeypatch):
    """Ohne die Angabe wäre ein Modellwechsel ein stilles Umschreiben."""
    core.set_setting("katalog_token", "geheim")
    gesehen = {}
    monkeypatch.setattr(hub, "katalog_hochladen",
                        lambda z: gesehen.update(zeilen=z) or
                        {"geschrieben": len(z)})
    main._katalog_zum_hub()
    nach_nr = {z["item_no"]: z for z in gesehen["zeilen"]}
    assert nach_nr["sw0010"]["modell"] == "qwen3-vl:latest"
    # Ohne Beschreibung kein Modell – sonst behauptete die Zeile eine
    # Herkunft, die es nicht gibt.
    assert nach_nr["sw0099"]["modell"] == ""


def test_neue_bildanalyse_wird_erkannt(abzug, monkeypatch):
    """Der Farblauf muss `updated_at` mitziehen, sonst bleibt sie unsichtbar."""
    core.set_setting("katalog_token", "geheim")
    monkeypatch.setattr(hub, "katalog_hochladen",
                        lambda z: {"geschrieben": len(z)})
    main._katalog_zum_hub()
    with core.db() as conn:
        conn.execute("UPDATE katalog_index SET merkmale = 'neu gesehen', "
                     "updated_at = 9999 WHERE item_no = 'sw0099'")
    assert main._katalog_zum_hub()["geschrieben"] == 1


# ------------------------------------- Die Gegenrichtung: abholen

def _hub_antwort(monkeypatch, seiten):
    """Den Hub vortäuschen – eine Liste von Antworten, Seite für Seite."""
    gefragt: list = []

    def fake(seit=0):
        gefragt.append(seit)
        return seiten[min(len(gefragt) - 1, len(seiten) - 1)]
    monkeypatch.setattr(hub, "katalog_holen", fake)
    return gefragt


def test_wer_nicht_selbst_abklappert_holt_den_abzug(abzug, monkeypatch):
    """Nerdfan, Paul und Kello haben weder BrickLink-Kontingent noch
    Sehmodell. Dieselbe Arbeit noch einmal zu leisten hieße Tage Abrufe und
    rund einen Tag Grafikeinheit – für dasselbe Ergebnis."""
    core.set_setting("crash_token", "berichts-token")
    _hub_antwort(monkeypatch, [
        {"zeilen": [{"item_no": "cas001", "item_type": "minifig",
                     "name": "Dragon Master", "such": "dragon master",
                     "merkmale": "cape yellow green dragon",
                     "farben": "red, blue", "art": "knight",
                     "img_url": "u", "jahr": 1993, "updated_at": 500}],
         "stand": 500, "mehr": False}])

    erg = main._katalog_vom_hub()
    assert erg["geholt"] == 1
    with core.db() as conn:
        r = conn.execute("SELECT name, merkmale, updated_at FROM "
                         "katalog_index WHERE item_no='cas001'").fetchone()
    assert r["name"] == "Dragon Master"
    assert r["merkmale"] == "cape yellow green dragon"
    assert int(core.get_setting("katalog_hub_geholt")) == 500


def test_die_quelle_holt_nichts_zurueck(abzug, monkeypatch):
    """Der Hub stempelt jede Zeile mit seiner eigenen Uhrzeit. Holte die
    Quelle ihre eigenen Zeilen zurück, überholte dieser Stempel ihren
    Wasserstand – und sie schöbe dieselbe Zeile beim nächsten Lauf wieder
    hoch. Ein Ping-Pong ohne Ende, das nur Kontingent verbrennt."""
    core.set_setting("crash_token", "berichts-token")
    core.set_setting("katalog_token", "schreib-token")
    gefragt = _hub_antwort(monkeypatch, [{"zeilen": [], "stand": 0,
                                          "mehr": False}])

    erg = main._katalog_vom_hub()
    assert erg["geholt"] == 0
    assert gefragt == [], "die Quelle hat beim Hub nachgefragt"


def test_ohne_hub_token_passiert_nichts(abzug, monkeypatch):
    gefragt = _hub_antwort(monkeypatch, [{"zeilen": [], "stand": 0,
                                          "mehr": False}])
    assert main._katalog_vom_hub()["geholt"] == 0
    assert gefragt == []


def test_mehrere_seiten_werden_durchgeblaettert(abzug, monkeypatch):
    core.set_setting("crash_token", "berichts-token")
    _hub_antwort(monkeypatch, [
        {"zeilen": [{"item_no": "a001", "updated_at": 10}],
         "stand": 10, "mehr": True},
        {"zeilen": [{"item_no": "a002", "updated_at": 20}],
         "stand": 20, "mehr": True},
        {"zeilen": [], "stand": 20, "mehr": False}])

    assert main._katalog_vom_hub()["geholt"] == 2
    assert int(core.get_setting("katalog_hub_geholt")) == 20


def test_ein_hub_der_immer_mehr_meldet_dreht_nicht_ewig(abzug, monkeypatch):
    """Sonst hinge der Zwölfstundenlauf für immer in dieser Schleife."""
    core.set_setting("crash_token", "berichts-token")
    gefragt = _hub_antwort(monkeypatch, [
        {"zeilen": [{"item_no": "a001", "updated_at": 10}],
         "stand": 10, "mehr": True}])

    main._katalog_vom_hub()
    assert len(gefragt) == main.KATALOG_HUB_SEITEN


def test_der_token_laesst_sich_hinterlegen_und_zuruecknehmen(abzug):
    import time as _t
    from fastapi.testclient import TestClient
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin,"
                     " is_dealer, created_at) VALUES ('sven','x',1,1,?)",
                     (int(_t.time()),))
    client = TestClient(main.app)
    client.headers["Authorization"] = "Bearer " + core.create_token(
        1, "sven", True)

    r = client.post("/api/settings/katalog_token", json={"token": "abc"})
    assert r.json()["quelle"] is True
    assert core.get_setting("katalog_token") == "abc"
    assert client.post("/api/settings/katalog_token",
                       json={"token": ""}).json()["quelle"] is False
