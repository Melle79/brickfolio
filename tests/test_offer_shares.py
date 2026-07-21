"""Tests für _distribute_offer_shares – Gesamtangebot anteilig nach Marktwert
auf die Artikel einer Einkaufsliste verteilen (Flohmarkt-Modus).
"""
import main


def test_sum_equals_total_exactly():
    shares = main._distribute_offer_shares(100.0, [10.0, 20.0, 30.0])
    assert round(sum(shares), 2) == 100.0


def test_proportional_to_market_value():
    # Werte 10/20/30 -> Anteile 1/6, 2/6, 3/6 von 60
    shares = main._distribute_offer_shares(60.0, [10.0, 20.0, 30.0])
    assert shares == [10.0, 20.0, 30.0]


def test_single_item_gets_full_total():
    assert main._distribute_offer_shares(42.5, [7.0]) == [42.5]


def test_rounding_remainder_lands_on_last_item():
    # 10 / 3 gleiche Gewichte: 3.33 + 3.33 + Rest 3.34 = 10.00
    shares = main._distribute_offer_shares(10.0, [5.0, 5.0, 5.0])
    assert shares == [3.33, 3.33, 3.34]
    assert round(sum(shares), 2) == 10.0


def test_unpriced_item_uses_average_weight():
    # Zwei bewertete Artikel (10, 30) -> Ø 20 als Gewicht für den dritten.
    # Gewichte 10/30/20 = Summe 60; von 60 -> 10 / 30 / 20
    shares = main._distribute_offer_shares(60.0, [10.0, 30.0, 0])
    assert shares == [10.0, 30.0, 20.0]
    assert round(sum(shares), 2) == 60.0


def test_all_unpriced_splits_evenly():
    # Keine Marktwerte -> gleichmäßige Verteilung, Rest am Ende
    shares = main._distribute_offer_shares(30.0, [0, 0, 0])
    assert shares == [10.0, 10.0, 10.0]
    assert round(sum(shares), 2) == 30.0


def test_zero_total_yields_zeros():
    shares = main._distribute_offer_shares(0.0, [10.0, 20.0])
    assert shares == [0.0, 0.0]
