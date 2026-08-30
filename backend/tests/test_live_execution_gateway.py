from __future__ import annotations

from datetime import datetime, timezone

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.execution_authorization_store import ExecutionAuthorizationStore
from app.live_execution_gateway import ExecutionMode, ExecutionPolicy, ExecutionSafetyError, LiveExecutionGateway
from app.order_intent import OrderIntent
from app.submission_intent_store import SubmissionIntentStore

SECRET = b"t" * 32

class FakeLiveExecutor:
    def __init__(self, result=None, error=None, recovered=None):
        self.result = result
        self.error = error
        self.recovered = recovered
        self.submit_calls = 0

    def submit_order(self, request):
        self.submit_calls += 1
        if self.error is not None:
            raise self.error
        return self.result

    def find_order_by_client_id(self, client_order_id):
        return self.recovered

class FakePositionReader:
    def get_positions(self):
        return []

class FakeReconciliationStateStore:
    def is_trading_blocked(self, **kwargs):
        return False

def make_order():
    return OrderIntent("NIFTY", "BUY", 100.0, 99.0, 102.0, 1, 1.0, "test", 0.8)

def make_context():
    observed_at = datetime.now(timezone.utc)
    base = BrokerExecutionContext("acct-1", "paper-route", "route-gen-1", 7, "snapshot", observed_at)
    signature = BrokerContextAttestor(SECRET).sign(
        account_id=base.account_id,
        broker_route=base.broker_route,
        route_generation=base.route_generation,
        generation=base.generation,
        snapshot_fingerprint=base.snapshot_fingerprint,
        observed_at=base.observed_at,
    )
    return BrokerExecutionContext(
        base.account_id, base.broker_route, base.route_generation, base.generation,
        base.snapshot_fingerprint, base.observed_at, signature,
    )

def make_request(client_order_id="client-1"):
    return BrokerOrderRequest(
        client_order_id=client_order_id,
        symbol="NIFTY", side="BUY", quantity=1, price=100, stop=99, target=102,
        broker_account_id=1, broker_route="paper-route", broker_route_generation="route-gen-1",
    )

def live_gateway(executor, intent_store):
    return LiveExecutionGateway(
        executor,
        ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=FakePositionReader(),
        local_positions_reader=lambda: [],
        authorization_store=ExecutionAuthorizationStore(":memory:"),
        context_attestor=BrokerContextAttestor(SECRET),
        reconciliation_state_store=FakeReconciliationStateStore(),
        submission_intent_store=intent_store,
    )

def authorize(gateway, request, context):
    return gateway.authorize_request(request, context)

def test_live_submission_creates_and_resolves_durable_intent(tmp_path):
    store = SubmissionIntentStore(tmp_path / "intents.json")
    executor = FakeLiveExecutor(result=BrokerOrderUpdate(order_id="b1", status="FILLED", client_order_id="client-1", symbol="NIFTY", side="BUY", quantity=1, filled_quantity=1, average_price=100))
    gateway = live_gateway(executor, store)
    request, context = make_request(), make_context()
    auth = authorize(gateway, request, context)
    gateway.execute_request(request, auth, context)
    assert executor.submit_calls == 1
    assert store.unresolved_count() == 0

def test_live_ambiguous_submission_leaves_intent_unresolved(tmp_path):
    store = SubmissionIntentStore(tmp_path / "intents.json")
    executor = FakeLiveExecutor(error=RuntimeError("timeout"), recovered=None)
    gateway = live_gateway(executor, store)
    request, context = make_request("client-ambiguous"), make_context()
    auth = authorize(gateway, request, context)
    try:
        gateway.execute_request(request, auth, context)
        assert False, "expected unknown broker order"
    except ExecutionSafetyError as exc:
        assert "outcome is unknown" in str(exc)
    assert store.unresolved_count() == 1
    assert store.unresolved()[0].client_order_id == "client-ambiguous"

def test_recovered_ambiguous_submission_resolves_intent(tmp_path):
    store = SubmissionIntentStore(tmp_path / "intents.json")
    recovered = BrokerOrderUpdate(order_id="b2", status="FILLED", client_order_id="client-recovered", symbol="NIFTY", side="BUY", quantity=1, filled_quantity=1, average_price=100)
    executor = FakeLiveExecutor(error=RuntimeError("timeout"), recovered=recovered)
    gateway = live_gateway(executor, store)
    request, context = make_request("client-recovered"), make_context()
    auth = authorize(gateway, request, context)
    gateway.execute_request(request, auth, context)
    assert store.unresolved_count() == 0

def test_intent_exists_on_disk_before_broker_submit(tmp_path):
    path = tmp_path / "intents.json"
    store = SubmissionIntentStore(path)
    observed = {"before_submit": False}

    class InspectingExecutor(FakeLiveExecutor):
        def submit_order(self, request):
            observed["before_submit"] = store.unresolved_count() == 1
            return BrokerOrderUpdate(order_id="b3", status="FILLED", client_order_id=request.client_order_id, symbol=request.symbol, side=request.side, quantity=request.quantity, filled_quantity=request.quantity, average_price=request.price)

    executor = InspectingExecutor()
    gateway = live_gateway(executor, store)
    request, context = make_request("client-before-submit"), make_context()
    auth = authorize(gateway, request, context)
    gateway.execute_request(request, auth, context)
    assert observed["before_submit"]
