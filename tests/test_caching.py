"""Versionierte Dateien dürfen die Browser behalten, alles andere nicht.

Die Versionsmarke kommt aus APP_VERSION – dadurch kann sie nicht vergessen
werden, und darauf beruht das dauerhafte Cachen.
"""
import pytest

import core
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "c.db"))
    core.init_db()
    return TestClient(main.app)


def test_startpage_carries_the_current_version(client):
    html = client.get("/").text
    assert "__APPVERSION__" not in html          # Platzhalter ist ersetzt
    assert f"/static/app.js?v={core.APP_VERSION}" in html
    assert f"/static/style.css?v={core.APP_VERSION}" in html


def test_anmeldeseite_zeigt_die_version(client):
    """Damit man sie beim Melden eines Fehlers nicht suchen muss."""
    html = client.get("/").text
    assert f"Brickfolio {core.APP_VERSION}" in html
    # Und zwar innerhalb der Anmeldeseite, nicht irgendwo.
    anmeldung = html[html.index('id="view-login"'):]
    assert f'class="login-version">Brickfolio {core.APP_VERSION}' in anmeldung


def test_startpage_is_never_cached(client):
    """Sie trägt die Versionsmarken – wird sie gecacht, kommt kein Update an."""
    assert client.get("/").headers["cache-control"] == "no-cache"


def test_versioned_asset_may_be_kept(client):
    r = client.get(f"/static/app.js?v={core.APP_VERSION}")
    assert r.status_code == 200
    assert "immutable" in r.headers["cache-control"]


def test_same_asset_without_version_is_revalidated(client):
    """Der Service Worker holt sie ohne Marke – die darf nicht festhängen."""
    r = client.get("/static/app.js")
    assert r.headers["cache-control"] == "no-cache"


def test_service_worker_and_manifest_are_revalidated(client):
    for path in ("/sw.js", "/manifest.webmanifest"):
        assert client.get(path).headers["cache-control"] == "no-cache"


def test_new_version_changes_every_asset_address(client, monkeypatch):
    """Ein Versionssprung muss alle Adressen erneuern – sonst wäre das lange
    Cachen eine Falle."""
    vorher = client.get("/").text
    monkeypatch.setattr(core, "APP_VERSION", "9.9.9")
    nachher = client.get("/").text
    assert "?v=9.9.9" in nachher
    assert vorher.count("?v=") == nachher.count("?v=") > 0
    assert vorher != nachher


def test_fonts_may_be_kept(client):
    """Schnitt steht im Dateinamen – eine andere Schrift wäre eine andere Datei."""
    r = client.get("/static/fonts/nunito-latin-800.woff2")
    assert r.status_code == 200
    assert "immutable" in r.headers["cache-control"]


def test_font_stylesheet_still_revalidates(client):
    """Die CSS-Datei darf sich ändern – sie holt sie über die Marke."""
    assert client.get("/static/fonts.css").headers["cache-control"] == "no-cache"
