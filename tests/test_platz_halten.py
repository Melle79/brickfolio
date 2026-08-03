"""Beim Auffrischen den Platz in der Liste behalten.

Die Sammlung baut sich blockweise auf (`kartenNachschub`), und ein Neuaufbau
fängt wieder beim ersten Block von 60 Karten an. Die Seite wird dabei kurz
sehr kurz – der Browser setzt das Fenster nach oben. Wer bei Nummer 300
stand, sah danach den Anfang.

Ausgelöst wurde das nicht nur, wenn jemand etwas anlegt: auch beim bloßen
Zurückkommen aus einem anderen Fenster und nach jedem Preisabruf, der einen
Kaufpreis nachträgt – dessen Summe steckt im Fingerabdruck.
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


def test_das_auffrischen_geht_ueber_mitplatz():
    assert "mitPlatz(loadCollection)" in block("ansichtAuffrischen")


def test_der_platz_wird_gemerkt_und_wieder_eingenommen():
    koerper = block("mitPlatz")
    assert "window.scrollY" in koerper, "die Höhe muss gemerkt werden"
    assert "window.scrollTo(0, hoehe)" in koerper, "und wieder eingenommen"


def test_es_werden_ebenso_viele_karten_nachgeschoben():
    """Ohne Nachschub bliebe die Seite kurz – dann liefe das Zurückspringen
    ins Leere, weil es die Höhe gar nicht mehr gibt."""
    koerper = block("mitPlatz")
    assert "nachschubLaden" in koerper
    assert re.search(r"querySelectorAll\(\"\.card\"\)\.length < vorher", koerper)


def test_der_nachschub_ist_begrenzt():
    """Eine `while`-Schleife über eine Funktion, die nichts mehr liefert,
    wäre eine Endlosschleife im Vordergrund."""
    koerper = block("mitPlatz")
    assert re.search(r"schutz\s*--", koerper)


def test_bei_offenem_popup_wird_nicht_aufgefrischt():
    """`renderCollection` schließt das Popup mit – wer gerade darin etwas
    einträgt, verlöre es mitten im Satz."""
    koerper = block("ansichtAuffrischen")
    assert 'getElementById("card-modal")' in koerper
    assert "auffrischenOffen = true" in koerper


def test_das_aufgeschobene_auffrischen_wird_nachgeholt():
    assert "auffrischenNachholen()" in block("closeCardModal")
    koerper = block("auffrischenNachholen")
    assert "ansichtAuffrischen()" in koerper
    # Beim Wechsel von einem Popup ins nächste bleibt der Merker stehen,
    # sonst ginge die Änderung ganz verloren.
    assert 'getElementById("card-modal")) return' in koerper
