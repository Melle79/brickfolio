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


# ------------------------------------------- Auch nach einer eigenen Änderung

def test_aenderungen_laden_ueber_sammlungAuffrischen():
    """Löschen, Nummer richtigstellen, Benachrichtigung übernehmen: Der
    nackte Aufruf warf dieselbe Stelle weg wie das Auffrischen – nur dass
    man die Änderung selbst ausgelöst hatte und trotzdem oben landete."""
    quelle = js()
    assert "function sammlungAuffrischen()" in quelle
    assert quelle.count("sammlungAuffrischen()") >= 10


def test_sortierung_und_filter_landen_weiter_oben():
    """Dort steht danach etwas anderes in der Liste – der Anfang ist die
    richtige Stelle. Bliebe hier der alte Platz, wäre es ein neuer Fehler."""
    quelle = js()
    for stelle in ('$("search").value = "";', "await saveSortPref(sel.value, false);"):
        i = quelle.index(stelle)
        assert "loadCollection();" in quelle[i:i + 200], f"{stelle} lädt nicht mehr schlicht"


def test_das_thema_wartet_auf_das_geschlossene_popup():
    """Man hat gerade „Setzen" gedrückt – da ist ein Neuaufbau, der das
    Popup mitnimmt, der falsche Moment."""
    quelle = js()
    assert 'if ($("sort").value === "theme") auffrischenSpaeter();' in quelle
    koerper = block("auffrischenSpaeter")
    assert 'getElementById("card-modal")' in koerper
    assert "auffrischenOffen = true" in koerper
    assert "ansichtAuffrischen()" in koerper, "ohne Popup sofort, sonst ginge es verloren"
