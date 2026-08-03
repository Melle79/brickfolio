"""Ein Fehlschlag vom Server gehört ins Protokoll.

Aufgezeichnet wurde bisher nur, was niemand auffing. Fast jeder Knopf fängt
seinen Fehler aber ab und schreibt ihn in eine Kurzmeldung – auf dem
Bildschirm stand „Fehler 502", und der Bericht meldete „keine Fehler".
Damit war die eine Frage, die zählt, nicht zu beantworten: **wo** kam er her?
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def block(name: str) -> str:
    quelle = js()
    anfang = quelle.index(f"function {name}(")
    return quelle[anfang:quelle.index("\n}", anfang)]


def test_api_meldet_einen_fehlschlag():
    assert "serverfehlerMelden(path, options, resp.status, text, roh)" in js()


def test_nur_ab_500():
    """Ein 404 („kennt BrickLink nicht") und ein 400 („Eingabe nicht gültig")
    sind gewöhnlicher Betrieb – die würden das Protokoll zumüllen."""
    koerper = block("serverfehlerMelden")
    assert re.search(r"code < 500", koerper)


def test_das_melden_meldet_sich_nicht_selbst():
    """`reportError` schickt selbst über `api` – ohne Ausnahme drehte sich
    das im Kreis, sobald genau dieser Weg fehlschlägt."""
    assert 'path.startsWith("/errors")' in block("serverfehlerMelden")


def test_der_weg_steht_dabei():
    """Ohne Pfad sagt „502" nichts: Der halbe Wert steckt darin, **welcher**
    Aufruf gescheitert ist."""
    koerper = block("serverfehlerMelden")
    assert "options.method" in koerper
    assert '/api" + path' in koerper


def test_der_anfang_der_antwort_wird_mitgeschrieben():
    """Der entscheidende Unterschied: Kommt der Fehler aus der App, ist das
    ihr JSON; kommt er von einem Zwischenserver, ist es dessen HTML-Seite.
    Ohne das sucht man an der falschen Stelle."""
    koerper = block("serverfehlerMelden")
    assert "roh" in koerper
    grenze = re.search(r"\.slice\(0, (\d+)\)", koerper)
    assert grenze and int(grenze.group(1)) <= 500, "sonst sprengt es das Feld"
