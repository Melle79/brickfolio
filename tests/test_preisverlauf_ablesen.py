"""Preis und Datum im Verlauf ablesen – am Zeiger und am Finger.

Am Rechner fährt man mit der Maus über die Kurve und liest mit; fährt man
weg, soll nichts kleben bleiben. Am Telefon ist es genau andersherum: Zum
Ablesen muss man **loslassen**. Bis 2.88.13 verschwand der Preis genau in
dem Moment, in dem man ihn lesen wollte – ein `pointerup` blendete ihn am
Finger wieder aus.

Getroffen werden muss dabei die **Spalte**, nicht der Punkt: Auf dem
Telefon liegen die Punkte dicht beieinander, und der Finger verdeckt genau
den, den man treffen will.
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def _fn(name: str) -> str:
    m = re.search(r"(?:async )?function %s\([^)]*\) \{.*?\n\}\n" % name,
                  APP_JS.read_text(), re.S)
    assert m, "%s nicht gefunden" % name
    return m.group(0)


def test_der_finger_laesst_den_wert_stehen():
    """Kein `pointerup`, das am Finger ausblendet – das war der Fehler."""
    f = _fn("verlaufAblesen")
    m = re.search(r'addEventListener\("pointerup".*?\);', f, re.S)
    assert not m, "am Finger darf das Loslassen nichts ausblenden"


def test_der_zeiger_nimmt_ihn_mit():
    """Eine Maus fährt weiter; ein stehengebliebener Wert wäre dort falsch."""
    f = _fn("verlaufAblesen")
    m = re.search(r'addEventListener\("pointerleave",(.*?)\);', f, re.S)
    assert m, "pointerleave fehlt"
    assert 'pointerType === "mouse"' in m.group(1), (
        "nur der Zeiger soll den Wert mitnehmen")


def test_getroffen_wird_die_spalte_nicht_der_punkt():
    """Der Finger verdeckt den Punkt, den er treffen soll."""
    f = _fn("verlaufAblesen")
    assert "Math.abs(xVon(p.ts) - sx)" in f, (
        "gesucht wird der nächste Zeitpunkt zur Fingerposition")


def test_beide_kurven_werden_genannt():
    """Nur eine von beiden abzulesen ließe die interessantere Frage offen."""
    f = _fn("verlaufAblesen")
    assert "price_new" in f and "price_used" in f
