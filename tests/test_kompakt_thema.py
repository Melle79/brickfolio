"""Die kompakte Ansicht behält ihre Kacheln – auch nach Thema sortiert.

Am 25.09.2026 gemeldet: Nach Thema sortiert standen in der kompakten Ansicht
drei 400-px-Kästen je Reihe statt der 96-px-Kacheln. Die Desktop-Regel für
die Listenansicht (`:not(.grid-mode)`) traf auch `kompakt-mode`, hatte
dasselbe Gewicht wie die Kompakt-Regel und stand später – also gewann sie.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "style.css").read_text(
    encoding="utf-8")


def test_listen_spalten_schliessen_die_kompakte_ansicht_aus():
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", ohne_kommentare):
        wahl, block = m.group(1).strip(), m.group(2)
        if ("#collection-list" in wahl and ":not(.grid-mode)" in wahl
                and "minmax(400px" in block):
            assert ":not(.kompakt-mode)" in wahl, wahl
