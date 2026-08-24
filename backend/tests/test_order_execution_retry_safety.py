from app.idempotency_store import IdempotencyStore

class FakeBroker:
    def __init__(self):
        self.submissions = 0
        self.orders = {}

    def submit(self, client_order_id, symbol, quantity):
        self.submissions += 1
        if client_order_id in self.orders:
            return self.orders[client_order_id]
        order = {"broker_order_id": f"B-{self.submissions}", "client_order_id": client_order_id, "symbol": symbol, "quantity": quantity}
        self.orders[client_order_id] = order
        return order


def test_timeout_after_submit_then_retry_does_not_create_duplicate(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    broker = FakeBroker()
    client_id = "retry-safe-1"

    assert store.claim(client_id) is True
    first = broker.submit(client_id, "NIFTY", 1)
    store.mark_completed(client_id)

    assert store.claim(client_id) is False
    recovered = broker.submit(client_id, "NIFTY", 1)

    assert broker.submissions == 2
    assert first["broker_order_id"] == recovered["broker_order_id"]
    assert len(broker.orders) == 1


def test_unclaimed_retry_can_submit_once(tmp_path):
    store = IdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    broker = FakeBroker()
    client_id = "retry-safe-2"

    assert store.claim(client_id) is True
    order = broker.submit(client_id, "BANKNIFTY", 2)
    store.mark_completed(client_id)

    assert order["broker_order_id"] == "B-1"
    assert len(broker.orders) == 1
