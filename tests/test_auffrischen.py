"""Zurück am Tab wird die Ansicht aufgefrischt.

Solange nur der Browser in die Daten schrieb, genügte es, beim Wechsel der
Ansicht zu laden. Sobald es **mehr als einen Weg** gibt – das Handy eines
Familienmitglieds, ein zweiter Tab, ein Werkzeug an der Schnittstelle –,
sieht man sonst eine Liste, die es so nicht mehr gibt.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def auffrischer() -> str:
    quelle = js()
    anfang = quelle.index("function ansichtAuffrischen(")
    return quelle[anfang:quelle.index("\n}\n", anfang)]


def test_es_gibt_einen_auffrischer():
    assert "function ansichtAuffrischen(" in js()


def test_er_haengt_am_zurueckkommen():
    quelle = js()
    anfang = quelle.index('document.addEventListener("visibilitychange"')
    assert "ansichtAuffrischen()" in quelle[anfang:anfang + 500]


def test_der_scan_tab_bleibt_unberuehrt():
    """Dort steht ein Foto samt Treffern – das darf ein Fensterwechsel nicht
    wegräumen."""
    koerper = auffrischer()
    assert '"scan"' not in koerper
    for erwartet in ('"collection"', '"lists"', '"stats"'):
        assert erwartet in koerper, erwartet


def test_ohne_anmeldung_passiert_nichts():
    assert "if (!state.token) return;" in auffrischer()


def test_kurzes_wegklicken_loest_nichts_aus():
    """Wer zwischen zwei Fenstern hin- und herklickt, soll nicht bei jedem
    Klick ein Neuladen auslösen."""
    quelle = js()
    anfang = quelle.index('document.addEventListener("visibilitychange"')
    koerper = quelle[anfang:anfang + 500]
    assert "AUFFRISCH_PAUSE" in koerper
    assert "zuletztWeg" in koerper
    pause = re.search(r"const AUFFRISCH_PAUSE = (\d+)", quelle)
    assert pause and int(pause.group(1)) >= 1000


def test_ohne_ladeanzeige():
    """`loadCollection(true)` zeigt den Spinner – beim Auffrischen im
    Hintergrund würde das nur flackern."""
    assert "loadCollection()" in auffrischer()
    assert "loadCollection(true)" not in auffrischer()
