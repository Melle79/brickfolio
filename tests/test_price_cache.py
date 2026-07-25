"""Tests für den kurzlebigen Preis-Cache in price_guide (use_cache).

Katalog-Abfragen (Suche/Scan/Popup) dürfen denselben Preis kurz gecacht
wiederverwenden; gespeicherte Preise (Sammlung/Wunschliste) holen ohne Flag
weiterhin frisch.
"""
import integrations


def _mock_request(monkeypatch, calls):
    def fake_request(bl_type, item_no, condition, scope, auth):
        calls.append((item_no, scope))
        return {"currency_code": "EUR", "avg_price": "5", "unit_quantity": 3}
    monkeypatch.setattr(integrations, "_price_request", fake_request)
    monkeypatch.setattr(integrations, "_bl_auth", lambda: None)


def test_second_cached_call_skips_bricklink(monkeypatch):
    integrations._PRICE_CACHE.clear()
    calls = []
    _mock_request(monkeypatch, calls)
    a = integrations.price_guide("minifig", "sw0001", "U", scope="",
                                 use_cache=True)
    b = integrations.price_guide("minifig", "sw0001", "U", scope="",
                                 use_cache=True)
    assert a == b
    assert len(calls) == 1          # zweiter Aufruf aus dem Cache


def test_without_flag_always_fresh(monkeypatch):
    integrations._PRICE_CACHE.clear()
    calls = []
    _mock_request(monkeypatch, calls)
    integrations.price_guide("minifig", "sw0002", "U", scope="")
    integrations.price_guide("minifig", "sw0002", "U", scope="")
    assert len(calls) == 2          # gespeicherte Preise: immer frisch


def test_cache_separates_by_condition_and_region(monkeypatch):
    integrations._PRICE_CACHE.clear()
    calls = []
    _mock_request(monkeypatch, calls)
    integrations.price_guide("minifig", "sw0003", "U", scope="", use_cache=True)
    integrations.price_guide("minifig", "sw0003", "N", scope="", use_cache=True)
    integrations.price_guide("minifig", "sw0003", "U", scope="DE",
                             use_cache=True)
    assert len(calls) == 3          # Zustand/Region sind eigene Schlüssel


def test_cache_expires_after_ttl(monkeypatch):
    integrations._PRICE_CACHE.clear()
    calls = []
    _mock_request(monkeypatch, calls)
    monkeypatch.setattr(integrations, "PRICE_CACHE_TTL", -1)   # sofort abgelaufen
    integrations.price_guide("minifig", "sw0004", "U", scope="", use_cache=True)
    integrations.price_guide("minifig", "sw0004", "U", scope="", use_cache=True)
    assert len(calls) == 2
