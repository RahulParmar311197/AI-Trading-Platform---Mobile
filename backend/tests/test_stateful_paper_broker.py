import pytest
from app.broker_adapter import BrokerOrderRequest, BrokerOrderStatus, PaperBrokerAdapter


def request(order_id="paper-1", quantity=10):
    return BrokerOrderRequest(client_order_id=order_id, symbol="NIFTY", side="BUY", quantity=quantity)


def test_paper_broker_submission_is_idempotent_by_client_order_id():
    broker = PaperBrokerAdapter()
    first = broker.submit_order(request())
    second = broker.submit_order(request())
    assert first.client_order_id == second.client_order_id
    assert first.order_id != second.order_id or first.order_id == "PAPER-1"


def test_paper_broker_returns_normalized_terminal_state():
    broker = PaperBrokerAdapter()
    update = broker.submit_order(request("paper-2", 2))
    assert update.status == BrokerOrderStatus.FILLED.value
    assert update.client_order_id == "paper-2"
    assert update.symbol == "NIFTY"
    assert update.side == "BUY"
    assert update.quantity == 2


def test_paper_broker_cancel_is_terminal():
    broker = PaperBrokerAdapter()
    update = broker.submit_order(request("paper-3", 1))
    cancelled = broker.cancel_order(update.order_id)
    assert cancelled.status == BrokerOrderStatus.CANCELLED.value
    assert broker.get_order(update.order_id)["status"] == BrokerOrderStatus.CANCELLED.value


def test_paper_broker_rejects_non_positive_quantity():
    broker = PaperBrokerAdapter()
    with pytest.raises(ValueError, match="quantity must be positive"):
        broker.submit_order(request("paper-4", 0))


def test_client_order_reconciliation_returns_matching_order():
    broker = PaperBrokerAdapter()
    update = broker.submit_order(request("paper-reconcile", 3))
    recovered = broker.find_order_by_client_id("paper-reconcile")
    assert recovered is not None
    assert recovered["order_id"] == update.order_id
    assert recovered["client_order_id"] == "paper-reconcile"
