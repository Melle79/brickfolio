"""Die Neustart-Erkennung darf nicht an der Anmeldung hängen.

Nachgebaut am 29.08.2026: Während eines Updates ging die Sitzung verloren.
Danach schlug jeder Aufruf von `/update/status` fehl, die Seite erfuhr nie,
dass der Server zurück war – und die Sperre „Update wird installiert" stand,
bis jemand von Hand neu lud.
"""
import re
from pathlib import Path

import pytest

import core
import main
from fastapi.testclient import TestClient

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "lz.db"))
    core.init_db()
    return TestClient(main.app)


def test_laufzeit_antwortet_ohne_anmeldung(client):
    r = client.get("/api/laufzeit")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["version"] == core.APP_VERSION
    assert isinstance(d["started_at"], int) and d["started_at"] > 0


def test_laufzeit_verraet_nichts_weiter(client):
    """Nur Version und Startzeit – kein Countdown, kein Helferzustand."""
    d = client.get("/api/laufzeit").json()
    assert set(d) == {"version", "started_at"}


def test_update_status_bleibt_geschuetzt(client):
    """Der Rest gehört weiter hinter die Anmeldung."""
    assert client.get("/api/update/status").status_code == 401


def test_die_wache_faellt_auf_den_offenen_endpunkt_zurueck():
    """Im Fehlerzweig muss `/api/laufzeit` gefragt werden.

    Ohne das hängt die Sperre genau dann für immer, wenn sie am dringendsten
    weg müsste: nach einem Neustart, den die Seite nicht bemerken kann.
    """
    js = APP_JS.read_text()
    m = re.search(r"async function pollUpdateStatus\(\).*?\n\}\n", js, re.S)
    assert m, "pollUpdateStatus nicht gefunden"
    rumpf = m.group(0)
    fehlerzweig = rumpf[rumpf.index("} catch (_) {"):]
    assert "/api/laufzeit" in fehlerzweig, \
        "Der Fehlerzweig fragt den offenen Endpunkt nicht"
    assert "neustartPruefen" in fehlerzweig


def test_neustart_wird_nur_bei_aenderung_gemeldet():
    """Der erste gesehene Wert darf kein Neuladen auslösen."""
    js = APP_JS.read_text()
    m = re.search(r"function neustartPruefen\(startedAt\) \{.*?\n\}\n", js, re.S)
    assert m, "neustartPruefen nicht gefunden"
    f = m.group(0)
    # Erstkontakt merkt sich nur und meldet nichts.
    assert "serverStartedKnown === null" in f
    assert f.index("serverStartedKnown = startedAt") < f.index("neuLadenMit")
