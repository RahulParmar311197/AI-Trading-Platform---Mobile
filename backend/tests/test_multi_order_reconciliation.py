from app.broker_adapter import BrokerOrderRequest
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle, OrderStatus


class Router:
    def __init__(self, recovered):
        self.recovered = recovered

    def find_order_by_client_id(self, client_order_id):
        return self.recovered


def request(quantity=10):
    return BrokerOrderRequest(client_order_id="client-1", symbol="NIFTY", side="BUY", quantity=quantity)


def test_multi_order_reconciliation_aggregates_fills_and_weighted_average(tmp_path):
    recovered = {
        "multi_order": True,
        "client_order_id": "client-1",
        "orders": [
            {"order_id": "U1", "status": "complete", "filled_quantity": 6, "average_price": 100},
            {"order_id": "U2", "status": "complete", "filled_quantity": 4, "average_price": 110},
        ],
    }
    lifecycle = OrderLifecycle()
    service = OrderExecutionService(Router(recovered), lifecycle, ExecutionStateStore(str(tmp_path / "execution.json")))
    result = service.submit(request())
    assert result.status == "FILLED"
    assert result.broker_order_id == "U1,U2"
    assert lifecycle.orders["client-1"].filled_quantity == 10
    assert lifecycle.orders["client-1"].average_fill_price == 104


def test_multi_order_partial_fill_is_preserved(tmp_path):
    recovered = {
        "multi_order": True,
        "orders": [
            {"order_id": "U1", "status": "complete", "filled_quantity": 3, "average_price": 100},
            {"order_id": "U2", "status": "open", "filled_quantity": 2, "average_price": 110},
        ],
    }
    lifecycle = OrderLifecycle()
    service = OrderExecutionService(Router(recovered), lifecycle, ExecutionStateStore(str(tmp_path / "execution.json")))
    result = service.submit(request())
    assert result.status == "PARTIALLY_FILLED"
    assert lifecycle.orders["client-1"].filled_quantity == 5
    assert lifecycle.orders["client-1"].average_fill_price == 104


def test_multi_order_reconciliation_rejects_overfill(tmp_path):
    recovered = {"multi_order": True, "orders": [{"order_id": "U1", "status": "complete", "filled_quantity": 11, "average_price": 100}]}
    lifecycle = OrderLifecycle()
    service = OrderExecutionService(Router(recovered), lifecycle, ExecutionStateStore(str(tmp_path / "execution.json")))
    try:
        service.submit(request())
        assert False, "expected overfill protection"
    except RuntimeError as exc:
        assert "exceeds requested quantity" in str(exc)
