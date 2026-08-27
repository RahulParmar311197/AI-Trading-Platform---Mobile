from app.brokers.paper import PaperBrokerAdapter
from app.execution_adapter import submit_authorized
from app.execution_port import build_execution_request
from app.order_intent import OrderIntent
from app.risk_gateway import authorize


def test_authorized_order_executes_and_reconciles_on_paper_broker():
    broker = PaperBrokerAdapter({"NSE:TEST": 100.0})
    order = OrderIntent(symbol="NSE:TEST", side="BUY", quantity=1)
    auth = authorize(order=order, equity=100000, daily_pnl=0, open_positions=0)
    assert auth.allowed

    request = build_execution_request(order=order, authorization=auth, idempotency_key="e2e-1")
    receipt = submit_authorized(request, broker)

    assert receipt.status == "ACCEPTED"
    assert receipt.broker_order_id
    assert broker.get_order(receipt.broker_order_id)["status"] == "FILLED"
    assert broker.get_trades_for_order(receipt.broker_order_id)
    assert broker.get_positions() == [{"symbol": "NSE:TEST", "quantity": 1.0}]


def test_unauthorized_order_never_reaches_broker():
    broker = PaperBrokerAdapter({"NSE:TEST": 100.0})
    order = OrderIntent(symbol="NSE:TEST", side="BUY", quantity=1)
    auth = authorize(order=order, equity=100000, daily_pnl=-10000, open_positions=0)
    assert not auth.allowed

    try:
        build_execution_request(order=order, authorization=auth, idempotency_key="e2e-rejected")
    except ValueError:
        pass
    else:
        raise AssertionError("unauthorized request was accepted")

    assert broker.get_orders() == []
    assert broker.get_trades() == []
