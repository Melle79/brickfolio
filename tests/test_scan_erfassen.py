"""Die Trefferkarte im Scan und der Schritt danach – eine Hauptsache.

**Die Karte.** Vier gleich große Knöpfe mit demselben kräftigen Rahmen:
„＋ Zur Sammlung", „☆ Merken", „🛒 Liste", „BrickLink ↗". Sie sind sehr
unterschiedlich wichtig – die Sammlung will man fast immer, die Liste fast
nie, und BrickLink führt aus der App heraus. Weil sie nicht nebeneinander
passten, brach jede Beschriftung um („＋ Zur / Sammlung").

Jetzt derselbe Aufbau wie in der Katalogliste und im Steckbrief: ein
breiter Knopf, die Nebensachen als Zeichen, der Weg nach draußen als
Verweis (24.09.2026, Entwurf „D").

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
    assert '<button class="mini-btn add" data-add="${i}">${esc(tr("＋ Zur Sammlung"))}</button>' in f
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


def test_abbrechen_ist_ein_rotes_kreuz():
    """„und abrechen vielleicht als roten Knopf mit X" (24.09.2026) – in
    derselben Sprache wie der Löschen-Knopf der Sammlung, mit 44 Pixeln."""
    f = _scan()
    assert 'class="mini-btn zust-abbruch" data-cancel' in f
    assert 'aria-label="${esc(tr("Abbrechen"))}">✕</button>' in f
    m = re.search(r"\.zust-reihe \.zust-abbruch \{([^}]*)\}", css(), re.S)
    assert m
    r = m.group(1)
    assert "var(--red)" in r and "width: 44px" in r
    # die Höhe gilt für die ganze Reihe – Feld, Zustände und ✕ gleich hoch
    assert ".zust-reihe > * { min-height: 44px; }" in css()


def test_der_zustand_steht_in_einer_zeile():
    """**„Das würde auch alles auf eine Zeile passen."** (24.09.2026)

    Der erste Umbau (2.88.35) hatte noch eine eigene Zeile für den Hinweis
    und zwei Knöpfe über die volle Breite; das Feld zog sich auf der breiten
    Karte über 650 Pixel. Jetzt: feste Feldbreite, Knöpfe in ihrer
    natürlichen Größe, keine Extrazeile.
    """
    f = _scan()
    assert "zust-titel" not in f and "zust-wahl" not in f
    r = re.search(r"\.zust-reihe \.paid-input \{([^}]*)\}", css(), re.S)
    assert r and "flex: 0 1 120px" in r.group(1), "wachsen darf es nicht"
    k = re.search(r"\.zust-reihe \.mini-btn\.add \{([^}]*)\}", css(), re.S)
    assert k and "flex: 1 1 0" in k.group(1), (
        "die beiden Zustände füllen die Breite – sonst klebt alles links")


def test_sofort_speichern_steht_am_knopf():
    """Der Hinweis hat keine eigene Zeile mehr – er steht als Erklärung am
    Knopf, übersetzt."""
    f = _scan()
    assert 'title="${esc(tr("Als gebraucht aufnehmen"))}"' in f
    assert 'title="${esc(tr("Als neu aufnehmen"))}"' in f
    en = (FRONTEND / "i18n" / "en.json").read_text(encoding="utf-8")
    assert '"Als gebraucht aufnehmen"' in en and '"Als neu aufnehmen"' in en


# ---------------------------------------------------- die zweite Stelle

def test_auch_die_figurenliste_im_set_hat_das_rote_kreuz():
    """Im Steckbrief eines Sets lässt sich jede enthaltene Figur aufnehmen –
    mit demselben Zustands-Schritt. Dort war das ✕ noch schwarz, als
    einzige Stelle der App."""
    m = re.search(r"function wireFigActions\(out, figs\) \{.*?\n\}\n", js(), re.S)
    assert m
    f = m.group(0)
    assert 'class="mini-btn zust-abbruch" data-fcx' in f
    assert ".fig-actions .zust-abbruch {" in css()


# ---------------------------------------------------- Übersetzung

def test_trefferkarte_und_zurufe_laufen_durch_die_uebersetzung():
    """„＋ Zur Sammlung", „83 % sicher" und der Zuruf nach dem Aufnehmen
    standen als deutscher Text im Markup – auf Englisch las man dort
    Deutsch. Der Zuruf wurde sogar aus Teilen zusammengesetzt."""
    q = js()
    assert "% sicher</span>" not in q and "% sicher`" not in q
    assert "`Zur Sammlung hinzugefügt ✔ (" not in q
    assert ': "Zur Sammlung hinzugefügt ✔");' not in q
    en = (FRONTEND / "i18n" / "en.json").read_text(encoding="utf-8")
    for k in ('"{n} % sicher"', '"Zur Sammlung hinzugefügt ✔ ({zustand})"',
              '"＋ Zur Sammlung"'):
        assert k in en, k


# ---------------------------------------------------- auf eine Liste legen

def _cart() -> str:
    m = re.search(r"function wireCartButtons\(.*?\n\}\n", js(), re.S)
    assert m
    return m.group(0)


def test_liste_zustand_ist_eine_pille():
    """Zwei umrandete Knöpfe, einer gelb, lasen sich wie zwei Befehle – es ist
    aber eine Wahl. Dieselbe Pille wie im Formular."""
    f = _cart()
    assert 'class="erf-wahl" role="radiogroup"' in f
    assert "cond-mini" not in f


def test_liste_abbrechen_ist_ein_rotes_kreuz():
    f = _cart()
    assert 'class="mini-btn zust-abbruch" data-cl-cancel' in f
    assert 'class="mini-btn zust-abbruch" data-cl-back' in f, (
        "ohne Listen bricht der Nebenknopf ab")
    assert 'class="mini-btn liste-zurueck" data-cl-back' in f, (
        "mit Listen führt er zurück zur Wahl")


def test_formular_listen_sind_nicht_mehr_gruen():
    """Vorher war jede Liste ein grüner Knopf – bei fünf Listen fünf grüne."""
    m = re.search(r"async function pickListForManual\(\) \{.*?\n\}\n", js(), re.S)
    assert m
    f = m.group(0)
    assert 'class="mini-btn add" data-ml=' not in f
    assert 'class="mini-btn zust-abbruch" data-ml-cancel' in f


def test_listentexte_werden_uebersetzt():
    q = _cart()
    for t in ('tr("Auf welche Liste?")', 'tr("Neue Einkaufsliste")',
              'tr("Anlegen & drauflegen")', 'tr("＋ Neue Liste")'):
        assert t in q, t
    assert "`Flohmarkt ${today}`" not in js()
