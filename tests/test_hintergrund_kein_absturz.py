"""Vom Betriebssystem geholt ist kein Absturz.

Wirft iOS eine App im Hintergrund aus dem Speicher, läuft `pagehide` nicht.
Für die Erkennung sah das aus wie ein Abbruch – und das war nicht bloß
unsauber, es hat zwei Wochen gekostet: Von 23 Abbrüchen im Archiv lagen am
19.08.2026 **15** nach einer Pause von einer bis achtunddreißig Stunden.
Aus einem davon (15.351 Elemente am 15.08., danach 8,7 Stunden Lücke) ist
die These entstanden, die Sammlung sei zu groß. Sie war es nicht: Weder das
iPhone mit 664 Bildern noch der Mac mit 886 Bildern ist daran gestorben.

Der Vermerk wird beim Wechsel in den Hintergrund gesetzt und beim
Zurückkommen gelöscht.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def test_der_vermerk_wird_gesetzt_und_wieder_geloescht():
    """Nur gesetzt wäre schlimmer als gar nicht: Dann gälte nach dem ersten
    Wechsel in den Hintergrund jeder spätere Absturz als harmlos."""
    quelle = js()
    assert "const DIAG_BG_KEY" in quelle
    i = quelle.index('spur(document.hidden ? "in den Hintergrund"')
    umfeld = quelle[i:i + 500]
    assert "setItem(DIAG_BG_KEY" in umfeld, "wird nicht gesetzt"
    assert "removeItem(DIAG_BG_KEY)" in umfeld, "wird nie wieder gelöscht"


def test_ohne_abschied_aber_im_hintergrund_ist_kein_absturz():
    quelle = js()
    # Die Zuweisung, nicht die Deklaration weiter oben.
    i = quelle.index("absturzZuvor = !punkt")
    zeile = quelle[i:i + 200]
    assert "!punkt.bg" in zeile, "der Hintergrund schlägt nicht auf absturzZuvor durch"


def test_ohne_zeitvergleich():
    """Anders als beim Abschiedszettel: Auf dem Schreibtisch misst ein
    verborgener Tab gedrosselt weiter, sein letzter Messwert ist dann jünger
    als der Vermerk. Ein Vergleich mit der Zeit ginge dort schief."""
    quelle = js()
    i = quelle.index("const hintergrund = Number(")
    block = quelle[i:i + 400]
    assert "if (!punkt.sauber && hintergrund)" in block, \
        "die Zuordnung hängt an einem Zeitvergleich"


def test_getrennt_gezaehlt_statt_verschwiegen():
    """Die Fälle sollen sichtbar bleiben – nur eben in einer eigenen Zeile.
    Weggelassen wüsste man nachher nicht mehr, warum die Zahlen kleiner
    geworden sind."""
    quelle = js()
    assert "imHintergrund++" in quelle
    assert "lag die App im Hintergrund" in quelle


def test_im_verlauf_steht_es_dran():
    quelle = js()
    assert "im Hintergrund weggeräumt" in quelle, \
        "der Text zeigt sie weiterhin als OHNE ABSCHIED"


def test_die_laufzeit_vor_dem_absturz_zaehlt_sie_nicht_mit():
    """Eine Sitzung, die achtunddreißig Stunden im Hintergrund lag, verzerrt
    jede Aussage über die Laufzeit vor einem Absturz."""
    quelle = js()
    i = quelle.index('if (p2.g !== "start"')
    assert "p2.bg" in quelle[i:i + 120]
