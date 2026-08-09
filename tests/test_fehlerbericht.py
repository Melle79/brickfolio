"""Fehlerberichte an den Hub – ein Kanal neben dem Tausch-Netzwerk.

Der Verlauf liegt im Browser des Nutzers und nirgends sonst. Für die
Absturzsuche fehlte damit genau das Stück, das die Frage entscheidet: Stürzt
es nur bei einem ab (dann liegt es an dessen Gerät) oder bei allen (dann an
der App)?

Gebaut mit **eigenem Token**, nicht mit dem des Tausch-Netzwerks. Der Grund
ist nicht Ordnungsliebe: Von vier Instanzen im Haushalt waren zwei Mitglied.
Ein Kanal am Mitgliedskonto hätte die Hälfte stumm gelassen – und zwar
ausgerechnet die, deren Berichte am meisten erklärt hätten. Umgekehrt gibt
niemand mit einem Bericht etwas über sein Tauschen preis.
"""
import time

import pytest

import core
import hub as hubmod
import main
from fastapi.testclient import TestClient


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "f.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('admin', 'x', 1, 1, ?)",
            (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "admin", True)
    return c


# ------------------------------------------------------------- Ohne Token

def test_ohne_token_sagt_die_instanz_das_offen(ctx):
    """Die Oberfläche entscheidet daran, ob sie „Senden" oder „Kopieren"
    anbietet. Ohne diese Auskunft wäre der Knopf bei der Hälfte der
    Instanzen tot, ohne dass es jemandem auffällt."""
    assert ctx.get("/api/diag/report").json() == {"can_send": False}


def test_ohne_token_wird_nichts_verschickt(ctx):
    r = ctx.post("/api/diag/report", json={"payload": "Verlauf …"})
    assert r.status_code == 409


# -------------------------------------------------------------- Mit Token

def test_mit_token_geht_der_bericht_raus(ctx, monkeypatch):
    core.set_setting("crash_token", "bfr_test")
    gesendet = {}

    def fake(payload, app_version="", crashes=0, views=""):
        gesendet.update(payload=payload, app_version=app_version,
                        crashes=crashes, views=views)
        return {"ok": True}

    monkeypatch.setattr(hubmod, "send_crash_report", fake)
    r = ctx.post("/api/diag/report", json={
        "payload": "Brickfolio – Speicher-Verlauf\n…", "crashes": 2,
        "views": "scan (2×)"})
    assert r.status_code == 200
    assert gesendet["crashes"] == 2
    assert gesendet["views"] == "scan (2×)"
    assert gesendet["app_version"] == core.APP_VERSION


def test_der_hub_darf_nein_sagen(ctx, monkeypatch):
    """Klappt es nicht, muss das ankommen – sonst löscht die Oberfläche den
    Verlauf für einen Bericht, der nie angekommen ist."""
    core.set_setting("crash_token", "bfr_test")

    def kaputt(*a, **k):
        raise hubmod.HubError(401, "Kein gültiger Berichts-Token")

    monkeypatch.setattr(hubmod, "send_crash_report", kaputt)
    r = ctx.post("/api/diag/report", json={"payload": "x"})
    assert r.status_code == 502
    assert "Berichts-Token" in r.json()["detail"]


def test_leerer_bericht_wird_abgewiesen(ctx):
    core.set_setting("crash_token", "bfr_test")
    assert ctx.post("/api/diag/report", json={"payload": ""}).status_code == 422


# ------------------------------------------------- Der Token ist ein Geheimnis

# --------------------------------------------------------- Die Oberfläche

def js() -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / "frontend" / "app.js"
            ).read_text(encoding="utf-8")


def test_vorschau_und_versand_kommen_aus_derselben_quelle():
    """„Du siehst vorher, was rausgeht" ist nur wahr, solange beides aus
    einer Funktion kommt. Zwei Fassungen hätten früher oder später
    auseinandergelebt – und niemand hätte es gemerkt."""
    j = js()
    stelle = j[j.index("async function diagBerichtSenden"):][:2500]
    assert "const text = diagText();" in stelle
    assert "payload: text" in stelle, "gesendet wird etwas anderes als gezeigt"
    kopie = j[j.index('$("btn-diag-copy")'):][:200]
    assert "diagText()" in kopie, "Kopieren nimmt einen eigenen Weg"


def test_der_knopf_verschwindet_auch_nach_dem_senden():
    """Aus dem Betrieb: Nach dem Senden ist der Verlauf leer, und `renderDiag`
    steigt bei leerem Verlauf **früh** aus – an der Stelle vorbei, die den
    Knopf ausblendet. Er blieb stehen und lud dazu ein, denselben, gar nicht
    mehr vorhandenen Absturz ein zweites Mal zu senden."""
    j = js()
    frueh = j[j.index("Noch keine Messwerte"):][:600]
    assert "sendeBox.hidden = true" in frueh, (
        "der frühe Ausstieg blendet den Knopf nicht aus")


def test_erst_das_ja_des_hubs_dann_loeschen():
    """Umgekehrt wäre der Bericht weg und nirgends angekommen."""
    j = js()
    stelle = j[j.index("async function diagBerichtSenden"):][:2500]
    senden = stelle.index('await api("/diag/report"')
    loeschen = stelle.index("localStorage.removeItem(DIAG_KEY)")
    assert senden < loeschen, "der Verlauf wird vor der Bestätigung gelöscht"


def test_der_token_gilt_als_geheim():
    """Er darf nicht im Fehlerbericht der App landen – der kann als
    GitHub-Issue öffentlich werden."""
    import integrations
    assert "crash_token" in integrations.GEHEIME_SETTINGS


def test_der_token_ist_nicht_der_tausch_token(ctx, monkeypatch):
    """Getrennte Kanäle heißt getrennte Geheimnisse. Fiele der eine auf den
    anderen zurück, hinge der Bericht doch wieder am Mitgliedskonto."""
    core.set_setting("hub_token", "bft_tausch")
    core.set_setting("crash_token", "")
    assert hubmod.report_enabled() is False
    assert ctx.get("/api/diag/report").json()["can_send"] is False


def test_nur_admins_duerfen_den_token_setzen(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "g.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('finn', 'x', 0, ?)", (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "finn", False)
    assert c.post("/api/settings/crash_token",
                  json={"token": "bfr_x"}).status_code == 403


def test_berichten_darf_jeder(tmp_path, monkeypatch):
    """Es sind die eigenen Messwerte, und man hat sie vorher gesehen –
    dafür Admin zu verlangen wäre albern."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "h.db"))
    core.init_db()
    core.set_setting("crash_token", "bfr_test")
    monkeypatch.setattr(hubmod, "send_crash_report",
                        lambda *a, **k: {"ok": True})
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('finn', 'x', 0, ?)", (int(time.time()),)).lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "finn", False)
    assert c.post("/api/diag/report",
                  json={"payload": "x"}).status_code == 200
