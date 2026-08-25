from types import SimpleNamespace

from app.app_factory import create_app, create_resources
from app.broker_adapter import BrokerOrderRequest
from app.order_execution_service import OrderExecutionService


class FakeRouter:
    def find_order_by_client_id(self, client_order_id, broker_route):
        return None

    def submit(self, request, broker_route):
        return SimpleNamespace(order_id="broker-1", client_order_id=request.client_order_id, symbol=request.symbol, side=request.side, status="SUBMITTED", filled_quantity=0, average_price=None, price=None)


def test_live_execution_uses_shared_observability():
    resources = create_resources(execution_path=":memory:", idempotency_path=":memory:", safety_path=":memory:", audit_path=":memory:")
    app = create_app(resources=resources, broker_router=FakeRouter())
    assert app.state.execution_observability is resources.execution_observability

    startup = resources.startup_execution_state
    startup.execution_allowed = True
    service = OrderExecutionService(
        FakeRouter(),
        __import__("app.order_lifecycle", fromlist=["OrderLifecycle"]).OrderLifecycle(resources.audit_log),
        resources.execution_store,
        resources.idempotency_store,
        startup_state=startup,
        observability=resources.execution_observability,
        audit_log=resources.audit_log,
    )
    request = BrokerOrderRequest(client_order_id="obs-1", symbol="NIFTY", side="BUY", quantity=1, order_type="MARKET", broker_account_id=1, broker_route="test")
    service.submit(request)
    snapshot = resources.execution_observability.snapshot()
    assert snapshot.submissions == 1
    assert snapshot.submitted == 1
    assert snapshot.broker_latency_samples == 1
