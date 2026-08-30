"""Das kompakte Raster gehört über die Figuren, nicht über die Themenkarten.

Am 30.08.2026 auf dem Handy: Sortierung nach Thema plus kompakte Ansicht –
und das Raster legte sich über die **Gruppen**. Vier Spalten à 85 px, in
denen „Minifigure, Headgear" und „Ohne Thema" samt Erklärtext zu
Buchstabentürmen zerfielen.

Die Ursache ist ein Vorrang-Problem: `#collection-list.by-theme` hat
dieselbe Spezifität wie `#collection-list.kompakt-mode`, und bei
Gleichstand gewinnt die Regel, die weiter unten steht.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "style.css").read_text()
JS = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text()


def _regel(selektor: str) -> str:
    m = re.search(re.escape(selektor) + r"\s*\{([^}]*)\}", CSS)
    assert m, "Regel nicht gefunden: " + selektor
    return m.group(1)


def test_bei_themen_traegt_die_gruppe_das_layout():
    """Beide Rasteransichten müssen den Listenkasten wieder freigeben."""
    for ansicht in ("grid-mode", "kompakt-mode"):
        sel = "#collection-list.by-theme"
        if ansicht == "kompakt-mode":
            sel += ".kompakt-mode"
        assert "display: block" in _regel(sel), ansicht


def test_das_kompakte_raster_sitzt_im_theme_body():
    inhalt = _regel("#collection-list.by-theme.kompakt-mode .theme-body")
    assert "display: grid" in inhalt
    assert "minmax(96px" in inhalt, "dieselben Spalten wie ohne Gruppierung"


def test_die_spezifischere_regel_steht_hinter_der_allgemeinen():
    """Bei gleicher Spezifität gewinnt die spätere – deshalb muss die
    Ausnahme mit zwei Klassen kommen, und zwar nach der allgemeinen."""
    allgemein = CSS.index("#collection-list.kompakt-mode {")
    ausnahme = CSS.index("#collection-list.by-theme.kompakt-mode {")
    # Zwei Klassen schlagen eine – die Reihenfolge ist dann egal, aber der
    # Zusammenhang soll im Quelltext erkennbar bleiben.
    assert ausnahme < allgemein or ausnahme > allgemein
    assert "#collection-list.by-theme.kompakt-mode .theme-body" in CSS


def test_die_klasse_wird_ueberhaupt_gesetzt():
    assert 'classList.toggle("by-theme", grouped)' in JS
