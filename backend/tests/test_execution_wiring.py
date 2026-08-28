from datetime import datetime, timezone

import pytest

from app.app_factory import create_resources
from app.broker_execution_context import BrokerExecutionContext
from app.broker_snapshot import BrokerSnapshot
from app.live_execution_gateway import ExecutionMode, ExecutionPolicy, ExecutionSafetyError
from app.order_intent import OrderIntent
from app.reconciliation import ReconciliationEngine
from app.submission_intent_store import SubmissionIntentStore


SECRET = b"production-wiring-secret-" + (b"x" * 32)
OTHER_SECRET = b"other-production-secret-" + (b"y" * 32)


class _Executor:
    def __init__(self):
        self.orders = []

    def execute(self, order):
        self.orders.append(order)
        return {"accepted": True}


class _PositionReader:
    def get_positions(self):
        return []


def _resources(tmp_path):
    return create_resources(
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.sqlite3"),
        safety_path=str(tmp_path / "safety.json"),
        audit_path=str(tmp_path / "audit.jsonl"),
        alert_path=str(tmp_path / "alerts.sqlite3"),
        alert_event_path=str(tmp_path / "alert-events.sqlite3"),
        execution_authorization_path=str(tmp_path / "authorizations.sqlite3"),
        broker_context_attestation_secret=SECRET,
    )


def _coordinator_context(resources, tmp_path):
    intent_store = SubmissionIntentStore(str(tmp_path / "submission-intents.json"))
    engine = ReconciliationEngine(intent_store)
    coordinator = resources.create_reconciliation_coordinator(
        engine=engine,
        route="upstox:account:7",
        account_id="7",
        route_generation="account:7:g1",
        generation=3,
    )
    snapshot = BrokerSnapshot(
        orders=[],
        positions=[],
        broker_route="upstox:account:7",
        broker_account_id=7,
    )
    result = coordinator.reconcile(
        internal_orders=[],
        internal_positions=[],
        broker_snapshot=snapshot,
    )
    return result.context


def _order():
    return OrderIntent(
        symbol="NIFTY",
        side="BUY",
        entry=100.0,
        stop_loss=99.0,
        take_profit=102.0,
        quantity=1.0,
        risk_amount=1.0,
        source="test",
        confidence=1.0,
    )


def test_resources_share_one_attestor_between_reconciliation_and_live_gateway(tmp_path):
    resources = _resources(tmp_path)
    gateway = resources.create_live_execution_gateway(
        _Executor(),
        policy=ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=_PositionReader(),
        local_positions_reader=lambda: [],
    )
    context = _coordinator_context(resources, tmp_path)

    assert gateway.context_attestor is resources.broker_context_attestor
    assert resources.broker_context_attestor.verify(context)
    authorization = gateway.authorize(_order(), context)
    assert authorization._context_key == "|".join(str(v) for v in context.canonical_key)


def test_context_signed_by_different_secret_is_rejected_by_wired_gateway(tmp_path):
    resources = _resources(tmp_path)
    gateway = resources.create_live_execution_gateway(
        _Executor(),
        policy=ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=_PositionReader(),
        local_positions_reader=lambda: [],
    )
    context = _coordinator_context(resources, tmp_path)
    other_attestor = resources.broker_context_attestor.__class__(OTHER_SECRET)
    forged_attestation = other_attestor.sign(
        account_id=context.account_id,
        broker_route=context.broker_route,
        route_generation=context.route_generation,
        generation=context.generation,
        snapshot_fingerprint=context.snapshot_fingerprint,
        observed_at=context.observed_at,
    )
    forged_context = BrokerExecutionContext(
        account_id=context.account_id,
        broker_route=context.broker_route,
        route_generation=context.route_generation,
        generation=context.generation,
        snapshot_fingerprint=context.snapshot_fingerprint,
        observed_at=context.observed_at,
        attestation=forged_attestation,
    )

    with pytest.raises(ExecutionSafetyError, match="not coordinator-attested"):
        gateway.authorize(_order(), forged_context)


def test_resources_use_durable_authorization_store_for_gateway(tmp_path):
    resources = _resources(tmp_path)
    gateway_one = resources.create_live_execution_gateway(
        _Executor(),
        policy=ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=_PositionReader(),
        local_positions_reader=lambda: [],
    )
    gateway_two = resources.create_live_execution_gateway(
        _Executor(),
        policy=ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=_PositionReader(),
        local_positions_reader=lambda: [],
    )
    context = _coordinator_context(resources, tmp_path)
    authorization = gateway_one.authorize(_order(), context)

    gateway_two.execute(_order(), authorization, context)
    with pytest.raises(ExecutionSafetyError):
        gateway_two.execute(_order(), authorization, context)


def test_coordinator_context_is_timezone_aware(tmp_path):
    resources = _resources(tmp_path)
    context = _coordinator_context(resources, tmp_path)
    assert context.observed_at.tzinfo is not None
    assert context.observed_at.utcoffset() is not None
