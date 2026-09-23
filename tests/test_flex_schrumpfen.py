"""Flex-Kinder mit `width: 100%` brauchen `min-width: 0`.

**Die Regel dahinter.** Ein Flex-Kind schrumpft von sich aus nicht unter die
Breite seines Inhalts – die automatische Mindestgröße ist die
`min-content`-Breite. Bei einem Auswahlfeld ist das die längste Option, bei
einem Eingabefeld der Platzhaltertext. `width: 100%` hilft dagegen nicht:
Die Mindestgröße gewinnt.

**Warum es hier auffiel.** Safari hält sich strikt daran, Chromium
schrumpft von selbst. Am 23.09.2026 stand auf Svens iPhone das
Sortierfeld mit 175 px in einem 98 px breiten Rahmen und schob die
Sammlung seitlich auf – in der Nachbildung war bei vier Bildschirmbreiten,
allen Ansichten und 800 Einträgen nie etwas zu sehen. Vier Anläufe gingen
so ins Leere, bis die Messung auf dem Gerät selbst den Kasten nannte.

Diese Datei hält die Lehre fest: Wer in einem Flex-Rahmen ein Feld auf
`width: 100%` setzt, muss ihm auch das Schrumpfen erlauben.
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "style.css"


def _regel(auswahl: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(), flags=re.S)
    m = re.search(re.escape(auswahl) + r"\s*\{([^}]*)\}", text)
    assert m, "Regel %s nicht gefunden" % auswahl
    return m.group(1)


def test_das_auswahlfeld_darf_schrumpfen():
    regel = _regel(".select-wrap select")
    assert "width: 100%" in regel
    assert "min-width: 0" in regel, (
        "Ohne das bleibt das Feld so breit wie seine längste Option")


def test_das_suchfeld_darf_schrumpfen():
    regel = _regel(".search-wrap input")
    assert "width: 100%" in regel
    assert "min-width: 0" in regel


def test_die_rahmen_selbst_duerfen_auch_schrumpfen():
    """`min-width: 0` am Rahmen allein genügte nicht – das Kind bringt seine
    eigene Mindestgröße mit."""
    for auswahl in (".select-wrap", ".search-wrap"):
        assert "min-width: 0" in _regel(auswahl), auswahl
