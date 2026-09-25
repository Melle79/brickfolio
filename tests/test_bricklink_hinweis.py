"""BrickLinks Auflagen an die Anwendung.

Die API-Bedingungen verlangen zweierlei sichtbar **in der Anwendung**: einen
Hinweis im **Wortlaut** und eine Kontaktadresse, unter der Dritte den
Betreiber erreichen. Beides fehlte bis zum 25.09.2026 vollständig.

Der Wortlaut ist vorgeschrieben, nicht sinngemäß – deshalb steht er hier
Zeichen für Zeichen und nicht als Stichprobe.
"""
import re
import time
from pathlib import Path

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
INDEX = FRONTEND / "index.html"

WORTLAUT = ("The term ‘BrickLink’ is a trademark of the LEGO Group BrickLink. "
            "This application uses the BrickLink API but is not endorsed or "
            "certified by LEGO BrickLink, Inc.")


def _text(s: str) -> str:
    """Auszeichnung raus, Leerraum vereinheitlichen, Entities auflösen."""
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&lsquo;", "‘").replace("&rsquo;", "’")
          .replace("&amp;", "&").replace("&nbsp;", " "))
    return re.sub(r"\s+", " ", s).strip()


def _user(name, admin):
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, ?, ?, 0, ?)",
            (name, core.hash_password("pw1234"), int(admin), int(time.time())))
        return cur.lastrowid


def _client(uid, name, admin):
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, name, admin)
    return c


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "bl.db"))
    core.init_db()
    return {"admin": _client(_user("anna", True), "anna", True),
            "kid": _client(_user("bruno", False), "bruno", False)}


def test_pflichthinweis_steht_im_wortlaut_in_der_oberflaeche():
    assert WORTLAUT in _text(INDEX.read_text(encoding="utf-8")), (
        "Der von BrickLink vorgeschriebene Hinweis fehlt oder wurde "
        "umformuliert. Er ist wörtlich vorgegeben.")


def test_pflichthinweis_wird_nicht_uebersetzt():
    """Er ist auf Englisch vorgeschrieben – auch auf einer deutschen Seite.

    Stünde er als Schlüssel im Katalog, träfe ihn der Übersetzungslauf.
    """
    for katalog in (FRONTEND / "i18n").glob("*.json"):
        inhalt = katalog.read_text(encoding="utf-8")
        assert "is not endorsed or certified" not in inhalt, (
            f"{katalog.name} übersetzt den Pflichtwortlaut.")


def test_kontakt_wird_gespeichert_und_ausgeliefert(ctx):
    r = ctx["admin"].post("/api/settings/betreiber_kontakt",
                          json={"kontakt": "  wer@example.org  "})
    assert r.status_code == 200
    assert r.json()["kontakt"] == "wer@example.org"
    assert ctx["kid"].get("/api/config").json()["betreiber_kontakt"] \
        == "wer@example.org"


def test_kontakt_laesst_sich_wieder_leeren(ctx):
    ctx["admin"].post("/api/settings/betreiber_kontakt",
                      json={"kontakt": "wer@example.org"})
    ctx["admin"].post("/api/settings/betreiber_kontakt", json={"kontakt": ""})
    assert ctx["kid"].get("/api/config").json()["betreiber_kontakt"] == ""


def test_nur_der_admin_darf_ihn_setzen(ctx):
    r = ctx["kid"].post("/api/settings/betreiber_kontakt",
                        json={"kontakt": "fremd@example.org"})
    assert r.status_code == 403


def test_kontakt_faellt_nicht_in_fehlerberichte(ctx):
    """Sichtbar in der eigenen Instanz heißt nicht sichtbar in einem Issue."""
    assert "betreiber_kontakt" in integrations.GEHEIME_SETTINGS
    core.set_setting("betreiber_kontakt", "privat@example.org")
    assert "privat@example.org" not in main.scrub(
        "Verbindung fehlgeschlagen für privat@example.org")
