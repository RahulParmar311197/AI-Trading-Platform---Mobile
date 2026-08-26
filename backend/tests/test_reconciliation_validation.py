import pytest

from app.reconciliation_validation import validate_reconciliation_inputs


def test_valid_reconciliation_inputs_are_preserved():
    orders = [{"client_order_id": "c1", "quantity": 10, "filled_quantity": 5}]
    positions = [{"symbol": "NIFTY", "quantity": 10}]
    result = validate_reconciliation_inputs(orders, orders, positions, positions)
    assert result[0] == orders
    assert result[2] == positions


def test_missing_order_identity_fails_closed():
    with pytest.raises(ValueError, match="stable identity"):
        validate_reconciliation_inputs([{"quantity": 1}], [], [], [])


def test_duplicate_broker_order_identity_fails_closed():
    orders = [{"client_order_id": "c1", "quantity": 1}, {"client_order_id": "c1", "quantity": 1}]
    with pytest.raises(ValueError, match="duplicate broker order identity"):
        validate_reconciliation_inputs([], orders, [], [])


def test_overfilled_order_fails_closed():
    with pytest.raises(ValueError, match="exceeds quantity"):
        validate_reconciliation_inputs([], [{"order_id": "b1", "quantity": 10, "filled_quantity": 11}], [], [])


def test_invalid_numeric_value_fails_closed():
    with pytest.raises(ValueError, match="invalid broker order quantity"):
        validate_reconciliation_inputs([], [{"order_id": "b1", "quantity": "not-a-number"}], [], [])


def test_duplicate_position_symbol_fails_closed():
    positions = [{"symbol": "NIFTY", "quantity": 1}, {"symbol": "nifty", "quantity": 2}]
    with pytest.raises(ValueError, match="duplicate broker position symbol"):
        validate_reconciliation_inputs([], [], [], positions)


def test_unknown_position_side_fails_closed():
    positions = [{"symbol": "NIFTY", "quantity": 1, "side": "UNKNOWN"}]
    with pytest.raises(ValueError, match="unknown broker position side"):
        validate_reconciliation_inputs([], [], [], positions)
