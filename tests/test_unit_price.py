"""Tests für _unit_price – Ø-Stückpreis passend zum Zustand mit Fallback."""
import main


def test_new_uses_price_new():
    assert main._unit_price("new", 10.0, 5.0) == 10.0


def test_used_uses_price_used():
    assert main._unit_price("used", 10.0, 5.0) == 5.0


def test_new_falls_back_to_used_when_new_missing():
    # Kein Neupreis vorhanden -> Gebrauchtpreis als Ersatz
    assert main._unit_price("new", None, 5.0) == 5.0


def test_used_falls_back_to_new_when_used_missing():
    assert main._unit_price("used", 10.0, None) == 10.0


def test_zero_new_price_falls_back_to_used():
    # 0 gilt als "kein Preis" (falsy) und fällt auf den Gebrauchtpreis zurück
    assert main._unit_price("new", 0, 7.5) == 7.5


def test_both_missing_returns_none():
    assert main._unit_price("used", None, None) is None
