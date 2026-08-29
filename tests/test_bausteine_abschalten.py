"""Bausteine einzeln abschalten – halbieren statt raten.

Alle Absturz-Dumps auf Svens Rechner betreffen nur diese Seite. Der
Abbruch selbst steckt in Chromium (ein absichtlicher `EXC_BREAKPOINT`, in
Edge 151 wie in Chrome 152), aber etwas hier löst ihn aus. Der
Aufrufstapel trägt keine Namen, also ist Raten aussichtslos – fünf Versuche
am 29.08.2026, fünf Fehlschläge.

Was zählt, ist die Zuordnung hinterher: Was abgeschaltet war, muss im
Fehlerbericht stehen. Ohne das wäre die ganze Halbiererei wertlos.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text()


def test_die_vier_bausteine_gibt_es_ueberall():
    """Schalter, Wirkung und Bericht müssen dieselben Namen kennen."""
    quelle = js()
    css = (FRONTEND / "style.css").read_text()
    html = (FRONTEND / "index.html").read_text()
    for b in ("cv", "sticky", "blur", "sw"):
        assert f'data-aus="{b}"' in html, "Schalter fehlt: " + b
    assert '"cv", "sticky", "blur", "sw"' in quelle
    # Drei wirken über CSS, der vierte über die Registrierung.
    for b in ("cv", "sticky", "blur"):
        assert f"html.ohne-{b}" in css, "CSS fehlt: " + b
    assert 'ausLesen().includes("sw")' in quelle


def test_der_bericht_haelt_fest_was_aus_war():
    quelle = js()
    m = re.search(r"function diagMessen\(.*?\n\}\n", quelle, re.S)
    assert m, "diagMessen nicht gefunden"
    assert "aus: ausLesen()" in m.group(0)
    # Und es muss auch in der lesbaren Zeile auftauchen.
    assert 'p.aus ? "OHNE: " + p.aus' in quelle


def test_die_wahl_liegt_im_localstorage():
    """Sie muss einen Absturz und das Neuladen danach überleben, ohne dass
    vorher ein Server antworten muss – sonst liefe die Sitzung, die es zu
    messen gilt, kurz mit angeschaltetem Baustein an."""
    quelle = js()
    m = re.search(r"function ausLesen\(\) \{.*?\n\}\n", quelle, re.S)
    assert m
    assert "localStorage.getItem(AUS_KEY)" in m.group(0)
    # Und nur bekannte Namen – sonst schaltet ein Tippfehler still nichts.
    assert "AUS_BAUSTEINE.includes" in m.group(0)


def test_unbekannte_namen_werden_verworfen():
    quelle = js()
    m = re.search(r"function ausLesen\(\) \{.*?\n\}\n", quelle, re.S)
    assert "filter(" in m.group(0)


def test_der_offline_helfer_wird_wirklich_abgemeldet():
    """Nicht neu anzumelden genügt nicht – ein vorhandener läuft weiter."""
    quelle = js()
    m = re.search(r"async function swAbmelden\(abmelden\) \{.*?\n\}\n",
                  quelle, re.S)
    assert m
    assert "getRegistrations()" in m.group(0)
    assert "unregister()" in m.group(0)
