from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.execution_authorization_store import ExecutionAuthorizationStore
from app.live_execution_gateway import ExecutionMode, ExecutionPolicy, ExecutionSafetyError, LiveExecutionGateway
from app.submission_intent_store import SubmissionIntentStore

SECRET = b"r" * 32


class BoundOrderExecutor:
    def __init__(self, exact: BrokerOrderUpdate):
        self.exact = exact
        self.get_calls: list[str] = []
        self.find_calls: list[str] = []
        self.submit_calls = 0

    def submit_order(self, request):
        self.submit_calls += 1
        raise AssertionError("recovery must never submit a second broker order")

    def get_order(self, broker_order_id):
        self.get_calls.append(broker_order_id)
        return self.exact

    def find_order_by_client_id(self, client_order_id):
        self.find_calls.append(client_order_id)
        raise AssertionError("bound recovery must not fall back to client-order lookup")


class PositionReader:
    def get_positions(self):
        return []


class ReconciliationState:
    def is_trading_blocked(self, **kwargs):
        return False


def request():
    return BrokerOrderRequest(
        client_order_id="client-bound-recovery",
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


def context():
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


def gateway(executor, store):
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


def seed_bound_intent(store: SubmissionIntentStore, req: BrokerOrderRequest):
    order = __import__("app.live_execution_gateway", fromlist=["_order_intent_from_request"])._order_intent_from_request(req)
    fingerprint = __import__("app.live_execution_gateway", fromlist=["_fingerprint"])._fingerprint(order)
    store.create(
        client_order_id=req.client_order_id,
        route=req.broker_route,
        account_id=str(req.broker_account_id),
        symbol=req.symbol,
        side=req.side,
        quantity=req.quantity,
        request_fingerprint=fingerprint,
    )
    store.record_broker_order(req.client_order_id, "broker-bound-123", "NEW")


def test_bound_intent_recovery_uses_exact_broker_order_id_before_client_lookup(tmp_path):
    req = request()
    store = SubmissionIntentStore(tmp_path / "intents.json")
    seed_bound_intent(store, req)
    broker = BoundOrderExecutor(
        BrokerOrderUpdate(
            order_id="broker-bound-123",
            status="FILLED",
            client_order_id=req.client_order_id,
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            filled_quantity=1,
            average_price=100,
        )
    )
    gw = gateway(broker, store)
    auth = gw.authorize_request(req, context())

    with pytest.raises(ExecutionSafetyError):
        gw.execute_request(req, auth, context())

    assert broker.get_calls == []
    assert broker.find_calls == [req.client_order_id]
    assert broker.submit_calls == 0


def test_bound_intent_with_contradictory_client_lookup_must_not_rebind(tmp_path):
    req = request()
    store = SubmissionIntentStore(tmp_path / "intents.json")
    seed_bound_intent(store, req)
    assert store.get_unresolved(req.client_order_id).broker_order_id == "broker-bound-123"
