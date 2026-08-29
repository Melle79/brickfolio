"""Der Steckbrief ist in Abschnitte geteilt.

Er war über Monate gewachsen: zehn Blöcke hintereinander weg – Anzahl,
Zustand, Bezahlt, Tauschbörse, Thema, Notizen, BrickLink-Nummer, Verweise,
enthaltene Teile, Marktpreise – ohne erkennbaren Zusammenhang.
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def _details() -> str:
    js = APP_JS.read_text()
    m = re.search(r"function collCardDetails\(it\) \{.*?\n\}\n", js, re.S)
    assert m, "collCardDetails nicht gefunden"
    return m.group(0)


def test_die_vier_abschnitte_stehen_da():
    f = _details()
    for titel in ("Mein Exemplar", "Einordnung", "Nachschlagen",
                  "Marktpreise"):
        assert 'steckbriefTeil("%s"' % titel in f, titel


def test_die_reihenfolge_ist_die_gewohnte():
    """Anzahl und Zustand zuerst – das braucht man beim Erfassen als
    Erstes. Ausdrücklich so entschieden, nicht zufällig."""
    f = _details()
    # „Marktpreise" wird weiter oben gebaut (in `preise`) und unten nur
    # eingesetzt – geprüft wird deshalb die Reihenfolge im Ergebnis.
    ausgabe = f[f.index('<div class="card-details"'):]
    stellen = [ausgabe.index(t) for t in
               ("Mein Exemplar", "Einordnung", "Nachschlagen", "${preise}")]
    assert stellen == sorted(stellen), stellen
    meins = f[f.index("const meins ="):f.index("const einordnung =")]
    assert meins.index("Anzahl") < meins.index("Zustand")


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
    for ziel in ("data-qty", "data-cond", "data-notes", "data-theme",
                 "data-price-out", "data-history", "data-qty-val"):
        assert ziel in f, ziel
    # Die Preisfelder dürfen nicht hinter einer Bedingung verschwinden –
    # die Überschrift darüber schon, sonst stünde sie ohne Zugang über
    # nichts.
    felder = f[f.index("const preisfelder ="):f.index("const hatPreise")]
    assert "data-price-out" in felder and "?" not in felder
    assert "hatPreise" in f and 'steckbriefTeil("Marktpreise"' in f
