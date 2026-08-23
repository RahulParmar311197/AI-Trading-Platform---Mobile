import pytest

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.safety_state import SafetyStateStore


class Broker:
    def __init__(self, status="FILLED"):
        self.status = status

    def submit_order(self, request):
        return BrokerOrderUpdate(order_id="B-1", status=self.status, price=100.0)
    def cancel_order(self, order_id): raise NotImplementedError
    def get_order(self, order_id): raise NotImplementedError
    def get_orders(self): return []
    def get_positions(self): return []
    def get_account(self): return {}


def req():
    return BrokerOrderRequest(client_order_id="L-1", symbol="NIFTY", side="BUY", quantity=1, price=100)


def service(tmp_path, status="FILLED"):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    safety.clear()
    router = BrokerRouter([BrokerRoute("test", Broker(status))], "test", safety_store=safety)
    lifecycle = OrderLifecycle()
    return OrderExecutionService(router, lifecycle, ExecutionStateStore(str(tmp_path / "execution.json"))), lifecycle


def test_filled_order_updates_lifecycle_and_persists(tmp_path):
    svc, lifecycle = service(tmp_path)
    result = svc.submit(req())
    assert result.status == "FILLED"
    assert lifecycle.orders["L-1"].status == OrderStatus.FILLED
    assert lifecycle.positions["NIFTY"].quantity == 1


def test_rejected_broker_result_updates_lifecycle(tmp_path):
    svc, lifecycle = service(tmp_path, "REJECTED")
    result = svc.submit(req())
    assert result.status == "REJECTED"
    assert lifecycle.orders["L-1"].status == OrderStatus.REJECTED


def test_cancelled_broker_result_updates_lifecycle(tmp_path):
    svc, lifecycle = service(tmp_path, "CANCELLED")
    result = svc.submit(req())
    assert result.status == "CANCELLED"
    assert lifecycle.orders["L-1"].status == OrderStatus.CANCELLED


def test_partial_fill_updates_lifecycle(tmp_path):
    svc, lifecycle = service(tmp_path, "PARTIALLY_FILLED")
    result = svc.submit(req())
    assert result.status == "PARTIALLY_FILLED"
    assert lifecycle.orders["L-1"].status == OrderStatus.PARTIALLY_FILLED
    assert lifecycle.orders["L-1"].filled_quantity == 1


@pytest.mark.parametrize("status", ["TRANSIT", "PENDING", "OPEN", "ACKNOWLEDGED"])
def test_working_broker_status_maps_to_submitted(tmp_path, status):
    svc, lifecycle = service(tmp_path, status)
    result = svc.submit(req())
    assert result.status == "SUBMITTED"
    assert lifecycle.orders["L-1"].status == OrderStatus.SUBMITTED
