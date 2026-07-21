"""Tests für _set_bound_map – wie viele Figuren-Exemplare in eigenen Sets
stecken (Grundlage der Doppelzählungs-Vermeidung im Gesamtwert).
"""
import main
from conftest import add_contents, add_item


def test_no_sets_returns_empty(conn):
    add_item(conn, "sw0001a", "minifig", quantity=3)
    assert main._set_bound_map(conn) == {}


def test_set_without_matching_figure_binds_nothing(conn):
    add_item(conn, "75300-1", "set", quantity=1)
    add_contents(conn, "75300-1", "sw0001a", qty=1)
    # Figur ist nicht in der Sammlung -> nichts zu binden
    assert main._set_bound_map(conn) == {}


def test_binds_figures_contained_in_owned_set(conn):
    add_item(conn, "75300-1", "set", quantity=1, condition="used")
    add_contents(conn, "75300-1", "sw0001a", qty=2)
    fig_id = add_item(conn, "sw0001a", "minifig", quantity=3, condition="used")
    # Set enthält 2x die Figur -> 2 der 3 Exemplare sind gebunden
    assert main._set_bound_map(conn) == {fig_id: 2}


def test_set_quantity_multiplies_need(conn):
    add_item(conn, "75300-1", "set", quantity=2, condition="used")
    add_contents(conn, "75300-1", "sw0001a", qty=1)
    fig_id = add_item(conn, "sw0001a", "minifig", quantity=5, condition="used")
    # 2 Sets * 1 Figur = 2 gebunden
    assert main._set_bound_map(conn) == {fig_id: 2}


def test_binding_capped_at_available_quantity(conn):
    add_item(conn, "75300-1", "set", quantity=1, condition="used")
    add_contents(conn, "75300-1", "sw0001a", qty=5)
    fig_id = add_item(conn, "sw0001a", "minifig", quantity=2, condition="used")
    # Bedarf 5, aber nur 2 vorhanden -> maximal 2 gebunden
    assert main._set_bound_map(conn) == {fig_id: 2}


def test_prefers_same_condition_row(conn):
    add_item(conn, "75300-1", "set", quantity=1, condition="used")
    add_contents(conn, "75300-1", "sw0001a", qty=1)
    new_id = add_item(conn, "sw0001a", "minifig", quantity=1, condition="new")
    used_id = add_item(conn, "sw0001a", "minifig", quantity=1, condition="used")
    # Set ist "used" -> die zustandsgleiche (used) Zeile wird zuerst gebunden
    result = main._set_bound_map(conn)
    assert result == {used_id: 1}
    assert new_id not in result


def test_overflow_spills_to_other_condition(conn):
    add_item(conn, "75300-1", "set", quantity=1, condition="used")
    add_contents(conn, "75300-1", "sw0001a", qty=2)
    new_id = add_item(conn, "sw0001a", "minifig", quantity=1, condition="new")
    used_id = add_item(conn, "sw0001a", "minifig", quantity=1, condition="used")
    # Bedarf 2: zuerst die used-Zeile (1), dann Überlauf auf die new-Zeile (1)
    assert main._set_bound_map(conn) == {used_id: 1, new_id: 1}


def test_multiple_sets_accumulate_need(conn):
    add_item(conn, "75300-1", "set", quantity=1, condition="used")
    add_item(conn, "75301-1", "set", quantity=1, condition="used")
    add_contents(conn, "75300-1", "sw0001a", qty=1)
    add_contents(conn, "75301-1", "sw0001a", qty=1)
    fig_id = add_item(conn, "sw0001a", "minifig", quantity=4, condition="used")
    # Zwei verschiedene Sets brauchen je 1 -> 2 gebunden
    assert main._set_bound_map(conn) == {fig_id: 2}
