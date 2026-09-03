from __future__ import annotations

from datetime import datetime, timezone

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.execution_authorization_store import ExecutionAuthorizationStore
from app.live_execution_gateway import ExecutionMode, ExecutionPolicy, ExecutionSafetyError, LiveExecutionGateway
from app.submission_intent_store import SubmissionIntentStore

SECRET = b"r" * 32


class CountingExecutor:
    def __init__(self, recovered):
        self.recovered = recovered
        self.submit_calls = 0
        self.find_calls = 0

    def submit_order(self, request):
        self.submit_calls += 1
        raise AssertionError("duplicate broker submission")

    def find_order_by_client_id(self, client_order_id):
        self.find_calls += 1
        return self.recovered


class PositionReader:
    def get_positions(self):
        return []


class ReconciliationState:
    def is_trading_blocked(self, **kwargs):
        return False


def make_request(client_order_id="client-retry"):
    return BrokerOrderRequest(
        client_order_id=client_order_id,
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        price=100,
        stop=99,
        target=102,
        broker_account_id=1,
        broker_route="paper-route",
        broker_route_generation="route-gen-1",
    )


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


def make_gateway(executor, store):
    return LiveExecutionGateway(
        executor,
        ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=PositionReader(),
        local_positions_reader=lambda: [],
        authorization_store=ExecutionAuthorizationStore(":memory:"),
        context_attestor=BrokerContextAttestor(SECRET),
        reconciliation_state_store=ReconciliationState(),
        submission_intent_store=store,
    )


def test_retry_of_existing_unresolved_intent_recovers_without_new_submission(tmp_path):
    store = SubmissionIntentStore(tmp_path / "intents.json")
    request = make_request()
    context = make_context()
    gateway_order = __import__("app.live_execution_gateway", fromlist=["_order_intent_from_request"])._order_intent_from_request(request)
    fingerprint = __import__("app.live_execution_gateway", fromlist=["_fingerprint"])._fingerprint(gateway_order)
    store.create(
        client_order_id=request.client_order_id,
        route=request.broker_route,
        account_id=str(request.broker_account_id),
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        request_fingerprint=fingerprint,
    )

    recovered = BrokerOrderUpdate(
        order_id="broker-recovered",
        status="FILLED",
        client_order_id=request.client_order_id,
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        filled_quantity=1,
        average_price=100,
    )
    executor = CountingExecutor(recovered)
    auth = gateway.authorize_request(request, context)

    result = gateway.execute_request(request, auth, context)

    assert executor.submit_calls == 0
    assert executor.find_calls == 1
    assert result.lifecycle.broker_order_id == "broker-recovered"
    assert store.unresolved_count() == 0


def test_existing_unresolved_intent_without_authoritative_match_blocks_submission(tmp_path):
    store = SubmissionIntentStore(tmp_path / "intents.json")
    request = make_request("client-unmatched")
    context = make_context()
    gateway_order = __import__("app.live_execution_gateway", fromlist=["_order_intent_from_request"])._order_intent_from_request(request)
    fingerprint = __import__("app.live_execution_gateway", fromlist=["_fingerprint"])._fingerprint(gateway_order)
    store.create(
        client_order_id=request.client_order_id,
        route=request.broker_route,
        account_id=str(request.broker_account_id),
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        request_fingerprint=fingerprint,
    )

    executor = CountingExecutor(None)
    gateway = make_gateway(executor, store)
    auth = gateway.authorize_request(request, context)

    try:
        gateway.execute_request(request, auth, context)
        assert False, "expected unresolved intent recovery failure"
    except ExecutionSafetyError as exc:
        assert "existing unresolved submission intent" in str(exc)

    assert executor.submit_calls == 0
    assert store.unresolved_count() == 1
