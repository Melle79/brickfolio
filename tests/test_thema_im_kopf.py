"""Das Thema steht im Kopf des Steckbriefs – und ohne Stift, wo es aus der
Nummer folgt.

`sw1213` ist Star Wars; da gibt es nichts zu entscheiden. An 910 Einträgen
nachgesehen (29.08.2026) hatte auch **nie jemand** etwas anderes gesetzt
als das Ableitbare. Bei eigenen Figuren, Teilen und unbekannten Kürzeln –
159 der 910 – weiß die App es dagegen nicht; dort bleibt der Stift die
einzige Möglichkeit.
"""
import re
import time
from pathlib import Path

import pytest

import core
import main
from fastapi.testclient import TestClient

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def _fn(name):
    m = re.search(r"function %s\([^)]*\) \{.*?\n\}\n" % name,
                  APP_JS.read_text(), re.S)
    assert m, "%s nicht gefunden" % name
    return m.group(0)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "tk.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at)"
            " VALUES ('sven', 'x', 1, ?)", (now,)).lastrowid
        for nr, art in (("sw0001a", "minifig"), ("custom-001", "minifig"),
                        ("3001", "part")):
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, quantity,"
                " added_at) VALUES (?, ?, ?, 1, ?)", (nr, art, nr, now))
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    return c


def test_der_server_sagt_ob_das_thema_feststeht(client):
    nach = {i["item_id"]: i for i in
            client.get("/api/collection").json()["items"]}
    assert nach["sw0001a"]["theme_auto"] is True
    # Eigene Figuren tragen zwar ein Thema („Custom"), aber ein Teil ohne
    # Kürzel nicht.
    assert nach["3001"]["theme_auto"] is False


def test_ohne_stift_wo_das_thema_feststeht():
    f = _fn("themaKopfzeile")
    assert "it.theme_auto" in f
    # Der Stift hängt an `fest`, nicht andersherum.
    assert 'const stift = fest ? ""' in f


def test_ohne_thema_steht_eine_einladung_da():
    """Bei einer eigenen Figur ohne Thema wäre eine leere Zeile nutzlos."""
    f = _fn("themaKopfzeile")
    assert 'tr("Thema setzen")' in f
    # Aber nur dort: Wo das Thema feststeht und keines da ist, gehört gar
    # nichts hin.
    assert "if (fest && !it.theme) return \"\";" in f


def test_die_zeile_steht_im_kopf_nicht_in_der_einordnung():
    js = APP_JS.read_text()
    m = re.search(r"function collCardDetails\(it\) \{.*?\n\}\n", js, re.S)
    assert m
    einordnung = m.group(0)[m.group(0).index("const einordnung ="):]
    einordnung = einordnung[:einordnung.index("const nachschlagen")]
    # Das Eingabefeld bleibt unten, die Anzeige nicht.
    assert "data-theme" in einordnung
    assert "data-thema-wert" not in einordnung
    assert "themaKopfzeile(item)" in js


def test_die_feste_zeile_weicht_nur_beim_bearbeiten():
    """Vorher verschwand sie, sobald kein Thema gesetzt war – jetzt zeigt
    sie dort die Einladung."""
    js = APP_JS.read_text()
    m = re.search(r"const zeigen = \(bearbeiten\) => \{.*?\n    \};", js, re.S)
    assert m, "zeigen nicht gefunden"
    assert "festRow.hidden = bearbeiten;" in m.group(0)
