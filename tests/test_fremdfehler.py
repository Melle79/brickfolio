"""„Script error." ist kein Fehler der App.

Der Browser schreibt das hin, wenn ein Skript **fremder Herkunft** geworfen
hat – Datei und Zeile verschweigt er dann aus Sicherheitsgründen. Die Seite
lädt nur eigene Dateien und kennt keine Rahmen, also kann es keins von uns
sein. Im Fehlerbericht stand der Eintrag trotzdem wie ein Defekt da.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
APP_JS = FRONTEND / "app.js"
INDEX = FRONTEND / "index.html"


def js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_erkennung_vorhanden():
    assert "function istFremdfehler(" in js()


def test_nur_ohne_datei_und_zeile():
    """Ein „Script error." *mit* Fundstelle wäre einer von uns – der muss
    weiterhin als echter Fehler durchgehen."""
    quelle = js()
    anfang = quelle.index("function istFremdfehler(")
    koerper = quelle[anfang:anfang + 400]
    assert "!filename" in koerper and "!lineno" in koerper


def test_meldung_haengt_die_spur_an():
    """Die Fundstelle fehlt – dann wenigstens, was zuletzt lief."""
    quelle = js()
    anfang = quelle.index("function initErrorReporting(")
    koerper = quelle[anfang:anfang + 1400]
    assert "istFremdfehler(" in koerper
    assert "spurAlsText()" in koerper


def test_bericht_beschriftet_den_eintrag():
    quelle = js()
    assert "function fremdfehlerZeile(" in quelle
    # Und die Beschriftung wird auch wirklich gezeichnet.
    anfang = quelle.index("function renderErrors(")
    assert "fremdfehlerZeile(e)" in quelle[anfang:anfang + 2000]


def test_alte_eintraege_werden_mitgenommen():
    """Vor 2.4.3 hießen sie „?:0" – die stehen ja noch in der Datenbank."""
    quelle = js()
    anfang = quelle.index("function fremdfehlerZeile(")
    assert '"?:0"' in quelle[anfang:anfang + 600]


def test_seite_laedt_keine_fremden_skripte():
    """Die Grundlage der ganzen Aussage: Käme ein fremdes Skript von uns,
    wäre die Beschriftung eine Lüge."""
    roh = INDEX.read_text(encoding="utf-8")
    quellen = re.findall(r'<script[^>]*\ssrc="([^"]+)"', roh)
    assert quellen, "Kein einziges Skript gefunden – Test greift ins Leere"
    for s in quellen:
        assert s.startswith("/static/"), f"Fremdes Skript: {s}"
    assert "<iframe" not in roh
