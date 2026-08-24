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
            BrokerOrderUpdate(
                order_id="broker-1",
                status="NEW",
                client_order_id="other-client",
            ),
        )


def test_symbol_side_and_quantity_mismatch_are_rejected():
    with pytest.raises(RuntimeError, match="different symbol"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(
                order_id="broker-1",
                status="NEW",
                symbol="BANKNIFTY",
            ),
        )

    with pytest.raises(RuntimeError, match="different side"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(
                order_id="broker-1",
                status="NEW",
                side="SELL",
            ),
        )

    with pytest.raises(RuntimeError, match="different requested quantity"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(
                order_id="broker-1",
                status="NEW",
                quantity=6,
            ),
        )


def test_non_numeric_broker_quantity_is_rejected():
    with pytest.raises(RuntimeError, match="invalid requested quantity"):
        OrderExecutionService._validate_submission_result(
            REQUEST,
            BrokerOrderUpdate(
                order_id="broker-1",
                status="NEW",
                quantity="five",
            ),
        )
