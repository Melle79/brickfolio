"""Tests für den Fehlerbericht und die Issue-Erstellung.

Wichtig sind zwei Dinge: Gleichartige Fehler dürfen die Liste nicht fluten,
und der GitHub-Token darf niemals in einem Issue landen – das ginge sonst
ausgerechnet an die Stelle, an die geschrieben wird.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _user(name, admin):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, 'x', ?, 1, ?)", (name, int(admin), now))
        return cur.lastrowid


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "err.db"))
    core.init_db()
    admin = TestClient(main.app)
    admin.headers["Authorization"] = (
        "Bearer " + core.create_token(_user("admin", True), "admin", True))
    kid = TestClient(main.app)
    kid.headers["Authorization"] = (
        "Bearer " + core.create_token(_user("kind", False), "kind", False))
    return {"admin": admin, "kid": kid}


def _report(client, message="Boom", detail=None, context=None):
    return client.post("/api/errors", json={
        "message": message, "detail": detail, "context": context})


# ------------------------------------------------------------ Melden

def test_error_is_stored(ctx):
    assert _report(ctx["kid"], "Kaputt").status_code == 200
    items = ctx["admin"].get("/api/errors").json()["items"]
    assert len(items) == 1
    assert items[0]["message"] == "Kaputt" and items[0]["count"] == 1
    assert items[0]["username"] == "kind"      # wer es gemeldet hat


def test_same_error_is_counted_not_duplicated(ctx):
    for _ in range(4):
        _report(ctx["kid"], "Immer wieder", detail="stack A")
    items = ctx["admin"].get("/api/errors").json()["items"]
    assert len(items) == 1 and items[0]["count"] == 4


def test_different_errors_are_separate(ctx):
    _report(ctx["kid"], "Fehler A")
    _report(ctx["kid"], "Fehler B")
    assert len(ctx["admin"].get("/api/errors").json()["items"]) == 2


def test_list_is_admin_only(ctx):
    _report(ctx["kid"])
    assert ctx["kid"].get("/api/errors").status_code == 403


def test_admin_can_clear(ctx):
    _report(ctx["kid"])
    assert ctx["admin"].delete("/api/errors").status_code == 200
    assert ctx["admin"].get("/api/errors").json()["items"] == []


# ------------------------------------------------------------ Issue anlegen

def test_issue_needs_token(ctx):
    _report(ctx["kid"])
    eid = ctx["admin"].get("/api/errors").json()["items"][0]["id"]
    assert ctx["admin"].post(f"/api/errors/{eid}/issue").status_code == 501


def test_issue_is_created_and_remembered(ctx, monkeypatch):
    core.set_setting("github_token", "geheim-token")
    _report(ctx["kid"], "Absturz", detail="Zeile 1")
    eid = ctx["admin"].get("/api/errors").json()["items"][0]["id"]

    calls = []

    class Resp:
        status_code = 201

        @staticmethod
        def json():
            return {"html_url": "https://github.com/x/y/issues/7"}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        return Resp()

    monkeypatch.setattr(main.requests, "post", fake_post)
    res = ctx["admin"].post(f"/api/errors/{eid}/issue").json()
    assert res["url"].endswith("/issues/7") and res["existed"] is False
    assert "Absturz" in calls[0]["json"]["title"]

    # Zweiter Versuch legt kein neues Issue an
    res2 = ctx["admin"].post(f"/api/errors/{eid}/issue").json()
    assert res2["existed"] is True and len(calls) == 1


def test_token_never_leaks_into_issue(ctx, monkeypatch):
    """Steht der Token versehentlich im Fehlertext, darf er nicht mitgehen."""
    core.set_setting("github_token", "geheim-token")
    _report(ctx["kid"], "Fehler", detail="Authorization: Bearer geheim-token")
    eid = ctx["admin"].get("/api/errors").json()["items"][0]["id"]

    sent = {}

    class Resp:
        status_code = 201

        @staticmethod
        def json():
            return {"html_url": "https://github.com/x/y/issues/8"}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.update(json)
        return Resp()

    monkeypatch.setattr(main.requests, "post", fake_post)
    ctx["admin"].post(f"/api/errors/{eid}/issue")
    assert "geheim-token" not in sent["body"]
    assert "***" in sent["body"]


def test_issue_reports_bad_token(ctx, monkeypatch):
    core.set_setting("github_token", "abgelaufen")
    _report(ctx["kid"])
    eid = ctx["admin"].get("/api/errors").json()["items"][0]["id"]

    class Resp:
        status_code = 401

        @staticmethod
        def json():
            return {}

    monkeypatch.setattr(main.requests, "post",
                        lambda *a, **k: Resp())
    r = ctx["admin"].post(f"/api/errors/{eid}/issue")
    assert r.status_code == 401 and "Token" in r.json()["detail"]


def test_token_setting_is_admin_only(ctx):
    assert ctx["kid"].post("/api/settings/github_token",
                           json={"token": "x"}).status_code == 403


# ------------------------------------------------ GitHub-Token: sichtbar?

def test_gespeicherter_token_wird_maskiert_gezeigt(ctx):
    """Ob überhaupt einer liegt, war bisher nur daran zu erkennen, dass der
    Melden-Knopf erschien – und der erscheint erst mit einem Fehler."""
    assert ctx['admin'].get("/api/errors").json()["token_masked"] == ""
    ctx['admin'].post("/api/settings/github_token",
                json={"token": "github_pat_11ABCDEF_geheim"})
    d = ctx['admin'].get("/api/errors").json()
    assert d["can_report"] is True
    assert d["token_masked"].endswith("heim")
    assert "github_pat" not in d["token_masked"]


def test_leerer_token_entfernt_ihn_wieder(ctx):
    ctx['admin'].post("/api/settings/github_token", json={"token": "github_pat_x1234"})
    r = ctx['admin'].post("/api/settings/github_token", json={"token": "  "})
    assert r.json()["set"] is False
    assert ctx['admin'].get("/api/errors").json()["token_masked"] == ""


def test_pruefung_ohne_token_sagt_das(ctx):
    r = ctx['admin'].post("/api/settings/github_token/test").json()
    assert r["ok"] is False and "Kein Token" in r["info"]


def test_pruefung_meldet_ungueltigen_token(ctx, monkeypatch):
    ctx['admin'].post("/api/settings/github_token", json={"token": "github_pat_alt"})

    class Antwort:
        status_code = 401
    monkeypatch.setattr(main.requests, "get", lambda *a, **k: Antwort())
    r = ctx['admin'].post("/api/settings/github_token/test").json()
    assert r["ok"] is False and "abgelaufen" in r["info"]


def test_pruefung_meldet_nicht_freigegebenes_repo(ctx, monkeypatch):
    ctx['admin'].post("/api/settings/github_token", json={"token": "github_pat_x"})

    class Antwort:
        status_code = 404
    monkeypatch.setattr(main.requests, "get", lambda *a, **k: Antwort())
    r = ctx['admin'].post("/api/settings/github_token/test").json()
    # Der Repo-Name steht als Platzhalter drin – sonst bräuchte jede
    # abweichende GITHUB_REPO-Einstellung einen eigenen Katalogeintrag.
    assert r["ok"] is False and "{repo}" in r["info"] and r["repo"]


def test_pruefung_bestaetigt_gueltigen_token(ctx, monkeypatch):
    ctx['admin'].post("/api/settings/github_token", json={"token": "github_pat_gut"})

    class Antwort:
        status_code = 200
    monkeypatch.setattr(main.requests, "get", lambda *a, **k: Antwort())
    r = ctx['admin'].post("/api/settings/github_token/test").json()
    assert r["ok"] is True and "{repo}" in r["info"]


def test_pruefung_ist_admin_sache(ctx):
    assert ctx["kid"].post("/api/settings/github_token/test").status_code == 403
