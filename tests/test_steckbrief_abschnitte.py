"""Der Steckbrief: Kopf, Blätter, Abschnitte.

Er war über Monate gewachsen: zehn Blöcke hintereinander weg – Anzahl,
Zustand, Bezahlt, Tauschbörse, Thema, Notizen, BrickLink-Nummer, Verweise,
enthaltene Teile, Marktpreise – ohne erkennbaren Zusammenhang. Am
29.08.2026 kamen vier Überschriften dazu, aufgeklappt blieb alles.

Seit dem Umbau auf das große Bild (23.09.2026) ist er zweigeteilt: Bild,
Name und die drei Zahlen – Bezahlt, Wert, Gewinn – stehen als Kacheln im
**Kopf**; alles andere liegt auf drei **Blättern**. Zuklappen war damals
verworfen worden, weil es „bei jedem Öffnen einen Tipper kostet". Das gilt
weiter, ist aber erledigt: Die Zahlen stehen über den Reitern und kosten
keinen.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
APP_JS = FRONTEND / "app.js"
STYLE = FRONTEND / "style.css"


def _details() -> str:
    js = APP_JS.read_text()
    m = re.search(r"function collCardDetails\(it\) \{.*?\n\}\n", js, re.S)
    assert m, "collCardDetails nicht gefunden"
    return m.group(0)


def _kopf() -> str:
    """Der Kopf des Popups – die Kennzahlen und das, was openCardModal baut."""
    js = APP_JS.read_text()
    teile = []
    for name in ("steckbriefKopfzahlen", "themaKopfzeile"):
        m = re.search(r"function %s\([a-z]+\) \{.*?\n\}\n" % name, js, re.S)
        assert m, "%s nicht gefunden" % name
        teile.append(m.group(0))
    a = js.index("function openCardModal(")
    teile.append(js[a:js.index("${collCardDetails(item)}", a)])
    return "".join(teile)


def test_die_abschnitte_stehen_da():
    f = _details()
    for titel in ("Mein Exemplar", "Einordnung", "Nachschlagen"):
        assert 'steckbriefTeil("%s"' % titel in f, titel


def test_die_blaetter_stehen_in_der_gewohnten_reihenfolge():
    """Exemplar, Preise, Mehr.

    Zwischenzeitlich standen die Preise vorn, damit das Meistgesuchte keinen
    Tipper kostet – der Grund, aus dem am 29.08.2026 gar nichts zugeklappt
    wurde. Seit die drei Zahlen (Bezahlt, Wert, Gewinn) als Kacheln **über**
    den Reitern stehen, ist er erledigt: Sie sind immer sichtbar, ohne jeden
    Tipper. Auf dem Preis-Blatt liegt nur noch das Nachschlagen im Detail."""
    f = _details()
    liste = f[f.index("const blaetter = ["):f.index("].filter(")]
    stellen = [liste.index(s) for s in ('"exemplar"', '"preise"', '"mehr"')]
    assert stellen == sorted(stellen), stellen


def test_ein_leeres_blatt_bekommt_keinen_reiter():
    """Dieselbe Regel wie bei den Abschnitten: keine Aufschrift über nichts.

    Und bleibt nur ein Blatt übrig, entfällt die Leiste ganz – ein einzelner
    Reiter ist keine Wahl, sondern nur eine Überschrift."""
    f = _details()
    assert "].filter(([, , inhalt]) => inhalt.trim());" in f
    assert "blaetter.length > 1" in f


def test_die_blaetter_schalten_ueber_hidden_und_nichts_ueberstimmt_es():
    """Die `hidden`-Falle: Eine eigene `display`-Regel schlägt das Attribut.

    Dann lägen alle drei Blätter stumm übereinander – im Quelltext sähe
    alles richtig aus, und nur der laufende Browser verriete es."""
    js = APP_JS.read_text()
    assert "blatt.hidden = blatt.dataset.blattInhalt" in js
    for regel in re.findall(r"\.sb-blatt[^{]*\{([^}]*)\}", STYLE.read_text()):
        assert "display:" not in regel.replace(" ", ""), regel


def test_die_drei_zahlen_stehen_im_kopf_die_bedienung_im_blatt():
    """Bezahlt, Wert und Gewinn sind Kennzahlen – Anzahl und Zustand nicht.

    Alle fünf waren gleich laute Zeilen unter »Mein Exemplar«. Wonach man
    das Fenster öffnet, ist aber fast immer eine der drei Zahlen; Anzahl
    und Zustand fasst man an, wenn man schon da ist. Die Zahlen dürfen im
    Blatt nicht noch einmal auftauchen, sonst stünden sie doppelt – genau
    das war der Einwand beim Durchsehen."""
    kopf, f = _kopf(), _details()
    for haken in ("data-paid", "data-profit"):
        assert haken in kopf, haken
        assert haken not in f, haken
    for haken in ("data-qty", "data-qty-val", "data-cond"):
        assert haken in f, haken
        assert haken not in kopf, haken


def test_die_notiz_gehoert_zum_exemplar():
    """Sie stand unter »Einordnung« so weit unten, dass sie beim Durchsehen
    der Entwürfe übersehen wurde. »Einordnung« bleibt für das, was man
    einmal richtigstellt: Thema und BrickLink-Nummer."""
    f = _details()
    meins = f[f.index("const meins ="):f.index("const einordnung =")]
    assert "data-notes" in meins
    einordnung = f[f.index("const einordnung ="):f.index("const nachschlagen =")]
    assert "data-notes" not in einordnung
    # Das Thema steht seit 23.09.2026 samt Eingabefeld im Kopf – sonst läge
    # das Feld auf einem Blatt, das beim Bearbeiten gar nicht offen ist.
    assert "data-theme" not in einordnung
    assert "data-fix-no" in einordnung


def test_ein_leerer_abschnitt_bekommt_keine_ueberschrift():
    """Ohne BrickLink-Zugang hätte „Nachschlagen" nichts zu zeigen. Eine
    Überschrift über nichts ist schlechter als keine."""
    js = APP_JS.read_text()
    m = re.search(r"function steckbriefTeil\([^)]*\) \{.*?\n\}\n", js, re.S)
    assert m, "steckbriefTeil nicht gefunden"
    assert 'if (!roh) return "";' in m.group(0)


def test_die_verdrahtung_findet_ihre_ziele_weiter():
    """Alles, was die Karte später beschriftet oder ausliest, muss im
    Dokument stehen – auch die Preisfelder ohne BrickLink-Zugang, sonst
    schreibt die Verdrahtung ins Leere."""
    f = _details()
    ganz = _kopf() + f
    for ziel in ("data-qty", "data-cond", "data-notes", "data-theme",
                 "data-price-out", "data-history", "data-qty-val",
                 "data-paid", "data-paid-src", "data-profit", "data-kaufbuch",
                 "data-share", "data-figs-out", "data-fig-sets", "data-sub"):
        assert ziel in ganz, ziel
    # Die Preisfelder dürfen nicht hinter einer Bedingung verschwinden –
    # das Blatt darüber schon, sonst hätte es ohne Zugang nichts zu zeigen.
    felder = f[f.index("const preisfelder ="):f.index("const hatPreise")]
    assert "data-price-out" in felder and "?" not in felder
    assert "hatPreise" in f
