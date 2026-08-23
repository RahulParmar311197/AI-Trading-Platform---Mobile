import pytest

from app.order_execution_service import OrderExecutionService


class Request:
    client_order_id = "client-1"
    symbol = "NIFTY"
    side = "BUY"
    quantity = 10


def test_recovered_client_id_mismatch_is_rejected():
    with pytest.raises(RuntimeError, match="different client_order_id"):
        OrderExecutionService._validate_recovered_identity(Request(), {"client_order_id": "client-2"})


def test_recovered_symbol_mismatch_is_rejected():
    with pytest.raises(RuntimeError, match="different symbol"):
        OrderExecutionService._validate_recovered_identity(Request(), {"symbol": "BANKNIFTY"})


def test_recovered_side_mismatch_is_rejected():
    with pytest.raises(RuntimeError, match="different side"):
        OrderExecutionService._validate_recovered_identity(Request(), {"side": "SELL"})


def test_recovered_quantity_mismatch_is_rejected():
    with pytest.raises(RuntimeError, match="different requested quantity"):
        OrderExecutionService._validate_recovered_identity(Request(), {"quantity": 9})


def test_matching_recovered_identity_is_accepted():
    OrderExecutionService._validate_recovered_identity(
        Request(),
        {"client_order_id": "client-1", "symbol": "nifty", "side": "buy", "quantity": 10},
    )
