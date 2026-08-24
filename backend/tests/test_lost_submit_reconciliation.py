from app.broker_adapter import BrokerOrderRequest
from app.idempotency_store import IdempotencyStore

class AcceptThenLoseBroker:
    def __init__(self):
        self.orders = {}
        self.submits = 0

    def submit(self, request):
        self.submits += 1
        order = self.orders.get(request.client_order_id)
        if order is None:
            order = {"broker_order_id": "BROKER-1", "client_order_id": request.client_order_id, "symbol": request.symbol, "side": request.side, "quantity": request.quantity}
            self.orders[request.client_order_id] = order
        return order

    def find_by_client_order_id(self, client_order_id):
        return self.orders.get(client_order_id)


def test_lost_submit_response_reconciles_existing_broker_order(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    broker = AcceptThenLoseBroker()
    request = BrokerOrderRequest(client_order_id="lost-response-1", symbol="NIFTY", side="BUY", quantity=1)

    assert store.claim(request.client_order_id) is True
    broker.submit(request)  # broker accepted; response is lost

    assert store.claim(request.client_order_id) is False
    recovered = broker.find_by_client_order_id(request.client_order_id)
    assert recovered is not None
    assert recovered["broker_order_id"] == "BROKER-1"
    assert recovered["client_order_id"] == request.client_order_id
    assert broker.submits == 1


def test_reconciliation_requires_matching_order_identity(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    broker = AcceptThenLoseBroker()
    request = BrokerOrderRequest(client_order_id="lost-response-2", symbol="NIFTY", side="BUY", quantity=1)
    assert store.claim(request.client_order_id) is True
    broker.submit(request)

    recovered = broker.find_by_client_order_id(request.client_order_id)
    assert recovered["symbol"] == request.symbol
    assert recovered["side"] == request.side
    assert recovered["quantity"] == request.quantity
