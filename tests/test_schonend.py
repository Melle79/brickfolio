"""Der schonende Bildmodus.

Diese App entpackt Fotos, malt sie auf Zeichenflächen, liest Bildpunkte aus
und kodiert wieder – Arbeit, die der Browser gern auf die Grafikeinheit
schiebt und die kaum eine andere Seite ihm gibt. Der schonende Modus geht
denselben Weg zu Fuß, im Hauptspeicher. Damit lässt sich prüfen, ob ein
Absturz von dort kommt.
"""
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def helfer() -> str:
    quelle = js()
    anfang = quelle.index("async function bildEntpacken(")
    return quelle[anfang:quelle.index("\n}\n", anfang)]


def test_standardmaessig_aus():
    assert 'localStorage.getItem(SCHONEND_KEY) === "1"' in js()


def test_schalter_ist_da():
    assert 'id="diag-schonend"' in (FRONTEND / "index.html").read_text(
        encoding="utf-8")


def test_entpacken_laeuft_nur_ueber_einen_weg():
    """Umginge eine Stelle den Helfer, wäre der Modus wertlos: Man schaltete
    ihn ein und der alte Weg liefe trotzdem weiter."""
    quelle = js()
    anfang = quelle.index("async function bildEntpacken(")
    ende = quelle.index("\n}\n", anfang)
    aussen = quelle[:anfang] + quelle[ende:]
    assert "createImageBitmap(" in quelle[anfang:ende]
    for nr, zeile in enumerate(aussen.splitlines(), 1):
        nackt = zeile.strip()
        if nackt.startswith(("//", "*", "/*")):
            continue                      # Kommentare dürfen ihn nennen
        assert "createImageBitmap(" not in nackt, f"Zeile {nr}: {zeile}"


def test_kein_decode_auf_einem_losen_bild():
    """`img.decode()` kam bei einem Bild, das nicht im Dokument hängt, nicht
    zurück – nachgemessen, der ganze Scan blieb daran stehen."""
    for nr, zeile in enumerate(helfer().splitlines(), 1):
        nackt = zeile.strip()
        if nackt.startswith(("//", "*", "/*")):
            continue                      # der Kommentar darf es erklären
        assert ".decode()" not in nackt, f"Zeile {nr}: {zeile}"


def test_masse_kommen_aus_dem_rueckgabewert():
    """Bei einem Bildelement wäre `.width` die Anzeigebreite, nicht die
    echte – Ausschnitte lägen dann daneben."""
    quelle = js()
    anfang = quelle.index("async function ausschnittBild(")
    koerper = quelle[anfang:quelle.index("\n}\n", anfang)]
    assert "werk.breite" in koerper and "werk.hoehe" in koerper
    assert ".bmp" not in koerper


def test_zeichenflaechen_gehen_ueber_den_gemeinsamen_weg():
    """Im schonenden Modus müssen sie im Hauptspeicher liegen."""
    quelle = js()
    assert "function flaeche2d(" in quelle
    assert "willReadFrequently: schonendAn || lesen" in quelle
