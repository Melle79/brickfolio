"""Die Update-Prüfung fragt nicht die GitHub-API.

Ohne Anmeldung erlaubt die API 60 Abfragen je Stunde und Internetanschluss –
geteilt mit jedem anderen Gerät dahinter. Ist das aufgebraucht, blieb der
Hinweis aus. Die Release-Seite leitet auf die neueste Fassung weiter und
zählt nicht mit.
"""
import time

import pytest

import core
import main
import requests
from fastapi.testclient import TestClient


class _Antwort:
    def __init__(self, status, ort=""):
        self.status_code = status
        self.headers = {"Location": ort} if ort else {}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "u.db"))
    core.init_db()
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, "
            "created_at) VALUES ('admin', 'x', 1, ?)",
            (int(time.time()),)).lastrowid
    monkeypatch.setattr(main, "_UPDATE_CACHE",
                        {"ts": 0.0, "data": None, "fehler_ts": 0.0,
                         "fehler": None})
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(
        uid, "admin", True)
    return c


def test_kein_aufruf_der_api():
    quelle = open(main.__file__, encoding="utf-8").read()
    for repo in ("brickfolio", "nupplo"):
        assert "api.github.com/repos/Melle79/%s/releases" % repo not in quelle


def test_neue_fassung_aus_der_weiterleitung(client, monkeypatch):
    gefragt = []

    def head(url, **kw):
        gefragt.append((url, kw.get("allow_redirects")))
        return _Antwort(302, "https://github.com/Melle79/brickfolio/"
                             "releases/tag/v99.0.0")
    monkeypatch.setattr(main.requests, "head", head)
    d = client.get("/api/update_check").json()
    assert d["latest"] == "99.0.0" and d["update_available"] is True
    assert d["url"].endswith("/releases/tag/v99.0.0")
    assert gefragt == [(main._UPDATE_SEITE, False)], \
        "der Weiterleitung wird nicht gefolgt"


def test_eigene_fassung_ist_kein_update(client, monkeypatch):
    monkeypatch.setattr(main.requests, "head", lambda url, **kw: _Antwort(
        302, "https://github.com/x/y/releases/tag/v" + core.APP_VERSION))
    d = client.get("/api/update_check").json()
    assert d["update_available"] is False


def test_fehlschlag_wird_gemerkt(client, monkeypatch):
    """Vorher fragte jeder Aufruf des Mehr-Tabs erneut."""
    zaehler = []

    def head(url, **kw):
        zaehler.append(1)
        raise requests.ConnectionError("weg")
    monkeypatch.setattr(main.requests, "head", head)
    assert "error" in client.get("/api/update_check").json()
    assert "error" in client.get("/api/update_check").json()
    assert len(zaehler) == 1
    # Von Hand erzwungen wird trotzdem gefragt.
    client.get("/api/update_check?force=1")
    assert len(zaehler) == 2


def test_ohne_weiterleitung_ist_es_ein_fehler(client, monkeypatch):
    monkeypatch.setattr(main.requests, "head",
                        lambda url, **kw: _Antwort(200))
    assert "error" in client.get("/api/update_check").json()


def test_folgt_dem_umzug_des_repos(client, monkeypatch):
    """Nach dem Umbenennen leitet GitHub erst auf den neuen Namen um, dann
    auf die Fassung. Bis 3.0.0 endete die Prüfung am ersten Sprung."""
    alt = "https://github.com/Melle79/brickfolio/releases/latest"
    neu = "https://github.com/Melle79/nupplo/releases/latest"
    monkeypatch.setattr(main, "_UPDATE_SEITE", alt)
    gefragt = []

    def head(url, **kw):
        gefragt.append(url)
        assert kw.get("allow_redirects") is False
        if url == alt:
            return _Antwort(301, neu)
        return _Antwort(302, "https://github.com/Melle79/nupplo/"
                             "releases/tag/v99.1.0")
    monkeypatch.setattr(main.requests, "head", head)
    d = client.get("/api/update_check").json()
    assert d["latest"] == "99.1.0" and d["update_available"] is True
    assert gefragt == [alt, neu]


def test_weiterleitung_nur_innerhalb_von_github(client, monkeypatch):
    monkeypatch.setattr(main.requests, "head", lambda url, **kw: _Antwort(
        302, "https://example.com/releases/tag/v99.0.0"))
    assert "error" in client.get("/api/update_check").json()


def test_weiterleitung_im_kreis_endet(client, monkeypatch):
    zaehler = []

    def head(url, **kw):
        zaehler.append(url)
        return _Antwort(301, "https://github.com/x/y/releases/latest")
    monkeypatch.setattr(main.requests, "head", head)
    assert "error" in client.get("/api/update_check").json()
    assert len(zaehler) == 3


def test_alter_repo_name_wird_zum_neuen():
    assert main.GITHUB_REPO == "Melle79/nupplo"
