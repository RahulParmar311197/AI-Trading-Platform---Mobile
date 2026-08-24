from types import SimpleNamespace

from app.api_order_reconciliation import reconcile_api_order_projection
from app.order_lifecycle import OrderLifecycle, OrderStatus


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.commits = 0

    def query(self, model):
        return FakeQuery(self.rows)

    def commit(self):
        self.commits += 1


def test_projection_reconciles_existing_api_order_from_lifecycle():
    api_order = SimpleNamespace(client_order_id="ABC", status="PENDING", broker_order_id=None, note=None, id=1)
    lifecycle = OrderLifecycle()
    lifecycle.create("ABC", "NIFTY", "BUY", 1)
    lifecycle.orders["ABC"].status = OrderStatus.FILLED
    lifecycle.orders["ABC"].broker_order_id = "BROKER-1"

    db = FakeSession([api_order])
    unresolved = reconcile_api_order_projection(db, lifecycle)

    assert unresolved == []
    assert api_order.status == "FILLED"
    assert api_order.broker_order_id == "BROKER-1"
    assert db.commits == 1


def test_projection_does_not_create_or_submit_missing_lifecycle_order_and_blocks_startup():
    api_order = SimpleNamespace(client_order_id="ABC", status="PENDING", broker_order_id=None, note=None, id=1)
    db = FakeSession([api_order])

    unresolved = reconcile_api_order_projection(db, OrderLifecycle())

    assert unresolved == ["ABC:MISSING_EXECUTION_LIFECYCLE"]
    assert api_order.status == "PENDING"
    assert db.commits == 0
