"""Die Ansicht gehört an den Messwert, nicht nur in die Spur.

Aus der Absturzsuche: Zwei bestätigte Abstürze (08. und 09.08.2026) standen
beide auf der Scan-Ansicht, bei identischem Zustand – 7 MB, 1007 Elemente,
6 Bilder. Ob das ein Muster oder Zufall ist, ließ sich nicht sagen: Die
Ansicht stand nur in der **Spur**, und die behält zwanzig Einträge und ist
nach einem Neustart weg. Über mehrere Abstürze hinweg war damit nichts zu
vergleichen.

Am Messpunkt bleibt sie erhalten. Der letzte Messwert **vor** einem Abbruch
sagt dann, wo die App stand, als sie starb.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def test_die_ansicht_kommt_aus_dem_dokument_nicht_aus_dem_speicher():
    """`localStorage` gehört allen Tabs gemeinsam und nennt die zuletzt
    *irgendwo* gewählte Ansicht – bei zwei offenen Fenstern also die
    falsche."""
    j = js()
    anfang = j.index("function sichtbareAnsicht")
    stelle = j[anfang:j.index("function tabsLesen", anfang)]
    assert "getElementById(\"view-\" + n)" in stelle
    assert "hidden" in stelle
    assert "localStorage" not in stelle, "die Ansicht käme aus dem Speicher"


def test_jeder_messwert_traegt_die_ansicht():
    assert re.search(r"if \(ansicht\) punkt\.a = ansicht;", js()), (
        "die Ansicht landet nicht am Messpunkt")


def test_die_ansicht_steht_im_verlauf():
    assert 'p.a ? "▸ " + p.a : ""' in js(), (
        "im Verlauf ist die Ansicht nicht zu sehen")


def test_gezaehlt_wird_die_ansicht_vor_dem_absturz():
    """Der Starteintrag nennt die Ansicht **nach** dem Neustart – das ist
    immer die zuletzt gemerkte und sagt über den Absturz nichts."""
    j = js()
    stelle = j[j.index("abbruch++;"):][:300]
    assert "vor && vor.a" in stelle, (
        "gezählt wird die Ansicht des Starteintrags statt der davor")


def test_die_zusammenfassung_nennt_die_ansichten():
    j = js()
    assert "absturzAnsichten" in j
    assert "zuletzt offen war dabei" in j, (
        "die Häufung nach Ansicht wird nirgends ausgegeben")


def test_mehrfache_werden_mit_anzahl_genannt():
    """Zweimal „scan" ist die Aussage – einmal „scan" ist nur ein Zufall."""
    stelle = js()[js().index("absturzAnsichten)"):][:400]
    assert "n > 1" in stelle and "×" in stelle


def test_alle_ansichten_sind_erfasst():
    """Fehlt eine in der Liste, taucht sie nie als Absturzort auf – und
    ausgerechnet die wäre dann unverdächtig."""
    j = js()
    liste = re.search(r"const DIAG_ANSICHTEN = \[([^\]]*)\]", j, re.S)
    assert liste, "DIAG_ANSICHTEN fehlt"
    erfasst = set(re.findall(r'"(\w+)"', liste.group(1)))
    umschalter = re.search(
        r'function showTab\(name\) \{\s*\[([^\]]*)\]', j, re.S)
    gezeigt = set(re.findall(r'"(\w+)"', umschalter.group(1)))
    assert erfasst == gezeigt, (
        f"nur in showTab: {gezeigt - erfasst}, nur in DIAG: {erfasst - gezeigt}")
