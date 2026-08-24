import pytest

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.order_execution_service import OrderExecutionService


REQUEST = BrokerOrderRequest(
    client_order_id="client-1",
    symbol="NIFTY",
    side="BUY",
    quantity=5,
)


def test_valid_submission_response_is_accepted():
    OrderExecutionService._validate_submission_result(
        REQUEST,
        BrokerOrderUpdate(
            order_id="broker-1",
            status="NEW",
            client_order_id="client-1",
            symbol="NIFTY",
            side="BUY",
            quantity=5,
        ),
    )


def test_valid_partial_fill_response_is_accepted():
    OrderExecutionService._validate_submission_result(
        REQUEST,
        BrokerOrderUpdate(
            order_id="broker-1",
            status="PARTIALLY_FILLED",
            client_order_id="client-1",
            symbol="NIFTY",
            side="BUY",
            quantity=5,
            filled_quantity=3,
            average_price=101.5,
        ),
    )


def test_filled_response_must_report_full_quantity():
    with pytest.raises(RuntimeError, match="FILLED with incomplete quantity"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="FILLED", filled_quantity=4, average_price=101),
        )


def test_filled_response_must_report_filled_quantity():
    with pytest.raises(RuntimeError, match="FILLED without filled quantity"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="FILLED", average_price=101),
        )


def test_partial_fill_requires_average_price():
    with pytest.raises(RuntimeError, match="without an average price"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="PARTIALLY_FILLED", filled_quantity=2),
        )


def test_invalid_fill_quantity_is_rejected():
    with pytest.raises(RuntimeError, match="invalid filled quantity"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="PARTIALLY_FILLED", filled_quantity=6, average_price=101),
        )


def test_invalid_average_price_is_rejected():
    with pytest.raises(RuntimeError, match="non-positive average price"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="PARTIALLY_FILLED", filled_quantity=2, average_price=0),
        )


def test_missing_broker_order_id_is_rejected():
    with pytest.raises(RuntimeError, match="no broker order id"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="", status="NEW"),
        )


def test_client_order_identity_mismatch_is_rejected():
    with pytest.raises(RuntimeError, match="different client_order_id"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="NEW", client_order_id="other-client"),
        )


def test_symbol_side_and_quantity_mismatch_are_rejected():
    with pytest.raises(RuntimeError, match="different symbol"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="NEW", symbol="BANKNIFTY"),
        )
    with pytest.raises(RuntimeError, match="different side"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="NEW", side="SELL"),
        )
    with pytest.raises(RuntimeError, match="different requested quantity"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="NEW", quantity=6),
        )


def test_non_numeric_broker_quantity_is_rejected():
    with pytest.raises(RuntimeError, match="invalid requested quantity"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(order_id="broker-1", status="NEW", quantity="five"),
        )
