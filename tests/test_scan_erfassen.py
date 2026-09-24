"""Die Trefferkarte im Scan und der Schritt danach – eine Hauptsache.

**Die Karte.** Vier gleich große Knöpfe mit demselben kräftigen Rahmen:
„＋ Zur Sammlung", „☆ Merken", „🛒 Liste", „BrickLink ↗". Sie sind sehr
unterschiedlich wichtig – die Sammlung will man fast immer, die Liste fast
nie, und BrickLink führt aus der App heraus. Weil sie nicht nebeneinander
passten, brach jede Beschriftung um („＋ Zur / Sammlung").

Jetzt derselbe Aufbau wie in der Katalogliste und im Steckbrief: ein
breiter Knopf, die Nebensachen als Zeichen, der Weg nach draußen als
Verweis (24.09.2026, Svens Wahl „D").

**Der Zustands-Schritt.** Ein Tipp auf den Zustand nimmt weiter sofort
auf – das ist der schnellste Weg in die Sammlung. Nur „Abbrechen" war so
groß wie das Hinzufügen selbst.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def _scan() -> str:
    m = re.search(r"function renderScanResults\(items\) \{.*?\n\}\n", js(), re.S)
    assert m
    return m.group(0)


def test_eine_hauptsache_zwei_zeichen():
    f = _scan()
    assert '<button class="mini-btn add" data-add="${i}">＋ Zur Sammlung</button>' in f
    assert 'class="mini-btn zeichen" data-want=' in f
    assert 'class="mini-btn zeichen" data-cart=' in f


def test_zeichen_haben_eine_ansage():
    """Ein Knopf, der nur ein Zeichen trägt, braucht einen Namen – für die
    Vorlesefunktion und für den Hinweis beim Darüberfahren."""
    f = _scan()
    for teil in ('data-want="${i}"\n          title=', 'aria-label="${esc(tr("Merken"))}"'):
        assert teil in f


def test_brickLink_ist_ein_verweis():
    f = _scan()
    assert 'class="mini-btn link"' not in f, "BrickLink war ein Knopf"
    assert "karte-weiter" in f


def test_ein_zeichen_bekommt_keine_beschriftung():
    """`wireWantButtons` schrieb nach dem Merken „⭐ Gemerkt" hinein – das
    hätte einen 46-Pixel-Knopf gesprengt."""
    m = re.search(r"function wireWantButtons\(.*?\n\}\n", js(), re.S)
    assert m
    f = m.group(0)
    assert 'btn.classList.contains("zeichen")' in f
    assert 'btn.classList.add("an")' in f


def test_der_zustand_nimmt_mit_einem_tipp_auf():
    """Kein Zwischenschritt: Die beiden Zustände sind die Knöpfe, die
    aufnehmen."""
    f = _scan()
    assert 'data-c="used"' in f and 'data-c="new"' in f
    assert "Hinzufügen" not in f[f.index("zust-reihe"):f.index("zust-reihe") + 900]


def test_abbrechen_ist_ein_verweis_mit_voller_trefferflaeche():
    f = _scan()
    assert 'class="zust-abbruch" data-cancel' in f
    m = re.search(r"\.zust-abbruch \{([^}]*)\}", css(), re.S)
    assert m and "min-height: 44px" in m.group(1), (
        "ein Verweis darf kleiner aussehen, aber nicht kleiner zu treffen sein")


def test_der_hinweis_wird_uebersetzt():
    """Der alte Satz stand ohne `tr()` im Markup und fehlte in en.json –
    auf Englisch stand dort weiter Deutsch."""
    assert 'tr("Zustand – wird sofort gespeichert")' in _scan()
    assert '"Zustand – wird sofort gespeichert"' in (
        FRONTEND / "i18n" / "en.json").read_text(encoding="utf-8")
