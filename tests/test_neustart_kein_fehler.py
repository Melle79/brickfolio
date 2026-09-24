"""Ein 502 während eines Neustarts ist kein Fehler.

Am 24.09.2026 kam ein Bericht „502 bei POST /api/hub/trades/sync". Die
Antwort begann mit Cloudflares HTML-Seite, nicht mit dem JSON der App – die
Anfrage hatte die Instanz also nie erreicht. Das Tunnelprotokoll zeigte den
Grund: 20:07:46 bis 20:08:03 war der Behälter weg (Ausrollen von 2.88.37),
und um 20:07:54 lief genau diese eine Hintergrundabfrage hinein.

Solche Berichte verschwinden, **ohne dass ein echter Ausfall verschwindet**:
Die App fragt nach 20 Sekunden `/api/laufzeit`, seit wann der Server läuft.
Ist er um den Fehler herum frisch gestartet, war es der Neustart; sonst wird
gemeldet.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def _fn() -> str:
    q = (FRONTEND / "app.js").read_text(encoding="utf-8")
    m = re.search(r"function serverfehlerMelden\(.*?\n\}\n", q, re.S)
    assert m
    return m.group(0)


def test_nur_zwischenserver_fehler_werden_geprueft():
    """Ein 500 der App selbst ist immer ein Fehler – der wird sofort gemeldet."""
    f = _fn()
    assert '[502, 503, 504].includes(code)' in f
    assert 'anfang.startsWith("<")' in f, (
        "nur die HTML-Seite eines Zwischenservers, nicht das JSON der App")


def test_gefragt_wird_ohne_anmeldung_und_ohne_api():
    """`api()` würde einen neuen Fehler melden, und die Anmeldung kann nach
    einem Neustart weg sein – `/api/laufzeit` braucht keine."""
    f = _fn()
    assert 'fetch("/api/laufzeit", { cache: "no-store" })' in f
    assert "api(" not in f.split("setTimeout", 1)[1]


def test_ein_frischer_neustart_schluckt_den_bericht():
    f = _fn()
    assert "lz.started_at * 1000 >= zeitpunkt - NEUSTART_SPIELRAUM_MS) return;" in f


def test_bleibt_der_server_weg_wird_gemeldet():
    f = _fn()
    teil = f.split("setTimeout", 1)[1]
    assert "catch (_)" in teil and teil.rstrip().count("melden();") >= 1


def test_laufzeit_liefert_den_startzeitpunkt():
    b = (FRONTEND.parent / "backend" / "main.py").read_text(encoding="utf-8")
    assert '"started_at": _STARTED_AT' in b
    assert "_STARTED_AT = int(time.time())" in b
