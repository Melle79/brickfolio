"""„Manuell erfassen" mit eigenen Bauteilen – und der Schatten, der die
ganze Seite grau machte.

**Der Schatten.** Der grüne „hier geschaut"-Rahmen auf dem Scanfoto dunkelt
mit `box-shadow: 0 0 0 9999px` das Foto um sich herum ab. Der Behälter
schnitt aber nicht ab – seit v1.78.0 (31.07.2026) lief der Schatten über
die **ganze Seite**. Nach jedem Scan war alles um 28 % dunkler; nur was eine
Ebene höher liegt, Kopfleiste und Trefferkarte, blieb hell. Im Betrieb galt es
am 24.09.2026 zuerst für einen grauen Hintergrund des Formulars, dann fiel
auf: „es wird grau, sobald ich ein Foto aufgenommen habe".

**Das Formular** (Svens Wahl „B"): Typ und Zustand als Pillen wie im
Steckbrief, Anzahl mit Plus/Minus, das Bild als Kachel statt des rohen
„Datei auswählen", unten die Knöpfe wie auf der Trefferkarte.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def html() -> str:
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


def _regel(wahl: str) -> str:
    m = re.search(re.escape(wahl) + r"\s*\{([^}]*)\}", css(), re.S)
    assert m, wahl
    return m.group(1)


# ---------------------------------------------------- der Schatten

def test_der_rahmenschatten_bleibt_im_foto():
    assert "9999px" in _regel(".scan-rahmen"), (
        "wenn der Rahmen anders abdunkelt, ist dieser Test gegenstandslos")
    assert "overflow: hidden" in _regel(".scan-bild"), (
        "ohne das läuft der Schatten über die ganze Seite")


def test_der_schlagschatten_des_fotos_bleibt():
    """`overflow: hidden` beschneidet auch den Schatten des Bildes darin –
    darum trägt ihn jetzt der Behälter, dessen eigener Schatten nicht
    beschnitten wird."""
    assert "box-shadow: var(--shadow)" in _regel(".scan-bild")
    assert "box-shadow: none" in _regel(".scan-bild img")


# ---------------------------------------------------- das Formular

def test_kein_systembauteil_mehr_sichtbar():
    """Die beiden Auswahlfelder und das Dateifeld sind noch da – aber
    unsichtbar."""
    h = html()
    assert '<select id="m-type" hidden' in h
    assert '<select id="m-cond" hidden' in h
    assert '<input id="m-img" type="file" accept="image/*" class="unsichtbar">' in h
    assert '<label for="m-img" class="mini-btn erf-bild-knopf">' in h


def test_die_ids_bleiben_wie_sie_waren():
    """Elf Stellen lesen `m-type`, sechs `m-cond`, sieben `m-qty` – keine
    davon musste angefasst werden, solange die Kennungen bleiben."""
    h = html()
    for kennung in ("m-type", "m-cond", "m-qty", "m-img", "m-img-preview",
                    "m-img-thumb", "m-img-clear", "m-img-from-scan",
                    "btn-manual-add", "btn-manual-want", "btn-manual-list"):
        assert 'id="%s"' % kennung in h, kennung


def test_jedes_setzen_zeichnet_die_pillen_nach():
    """Setzt der Code `m-type` oder `m-cond` direkt, feuert kein Ereignis –
    ohne `erfWahlZeichnen()` danach zeigten die Pillen den alten Wert."""
    q = js()
    for m in re.finditer(r'\$\("m-(?:type|cond)"\)\.value = [^;]+;', q):
        danach = q[m.end():m.end() + 160]
        assert "erfWahlZeichnen()" in danach, (
            "Setzen ohne Nachziehen: " + q[m.start():m.end()])


def test_die_pillen_loesen_change_aus():
    """Der Lauscher an `m-type` startet die Suche neu – er muss weiter
    greifen."""
    m = re.search(r"function erfassenVerdrahten\(\) \{.*?\n\}\n", js(), re.S)
    assert m
    assert 'new Event("change", { bubbles: true })' in m.group(0)


def test_plus_minus_bleibt_in_den_grenzen():
    m = re.search(r"function erfassenVerdrahten\(\) \{.*?\n\}\n", js(), re.S)
    assert "Math.min(999, Math.max(1, n))" in m.group(0)


def test_zur_sammlung_ist_ueberall_gruen():
    """Vorher war dieselbe Aktion hier gelb (`btn-primary`) und im Scan grün."""
    assert '<button id="btn-manual-add" class="mini-btn add">' in html()


def test_das_bild_entfernen_trifft_auf_44_pixeln():
    assert "inset: -10px" in _regel(".erf-bild-weg::after")


def test_der_bildknopf_erbt_nichts_vom_label():
    """„Bild wählen" ist ein `label` und erbte `margin: 14px 0 4px` und die
    graue Beschriftungsfarbe – es stand 5 px tiefer als „Vom Scan"."""
    r = _regel(".erf-bild-knopf")
    assert "margin: 0" in r and "color: var(--ink)" in r
