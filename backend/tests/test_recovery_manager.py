from datetime import datetime, timezone

import pytest

from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.reconciliation import ReconciliationEngine
from app.recovery_manager import StartupRecoveryManager
from app.safety_state import SafetyStateStore
from app.submission_intent_store import SubmissionIntentStore


def make_manager(tmp_path):
    return StartupRecoveryManager(
        ExecutionStateStore(str(tmp_path / "execution.json")),
        SafetyStateStore(str(tmp_path / "safety.json")),
        ReconciliationEngine(SubmissionIntentStore()),
    )


def verified_reconciliation(manager, snapshot_at=None):
    observed_at = snapshot_at or datetime.now(timezone.utc)
    engine = manager.reconciliation
    check = engine.check([], [], [], [])
    attestor = BrokerContextAttestor(b"r" * 32)
    fingerprint = "test-fingerprint"
    attestation = attestor.sign(
        account_id="12",
        broker_route="paper:account:12",
        route_generation="account:12:g1",
        generation=0,
        snapshot_fingerprint=fingerprint,
        observed_at=observed_at,
    )
    context = BrokerExecutionContext(
        account_id="12",
        broker_route="paper:account:12",
        route_generation="account:12:g1",
        generation=0,
        snapshot_fingerprint=fingerprint,
        observed_at=observed_at,
        attestation=attestation,
    )
    return engine.build_verified_result(
        check,
        context=context,
        reconciled_at=observed_at,
        open_orders_reconciled=True,
        positions_reconciled=True,
        submission_intents_resolved=0,
        broker_ready=True,
    ), context


def test_matching_broker_state_requires_verified_reconciliation(tmp_path):
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 10)
    lifecycle.transition("o1", OrderStatus.FILLED, 10, 100)
    ExecutionStateStore(str(tmp_path / "execution.json")).save(lifecycle)

    manager = make_manager(tmp_path)
    result = manager.startup(
        OrderLifecycle(),
        lambda: ([{"client_order_id": "o1", "status": "FILLED"}], [{"symbol": "NIFTY", "quantity": 10}]),
    )
    assert not result.ready
    assert result.reason == "VERIFIED_RECONCILIATION_REQUIRED"
    assert manager.trading_halted
    assert SafetyStateStore(str(tmp_path / "safety.json")).load().trading_halted


def test_verified_reconciliation_clears_safety_state(tmp_path):
    manager = make_manager(tmp_path)
    verified, context = verified_reconciliation(manager)

    result = manager.startup(
        OrderLifecycle(),
        lambda: ([], []),
        verified_reconciliation=verified,
        active_context=context,
    )

    assert result.ready
    assert result.reason == "RECOVERY_OK"
    state = SafetyStateStore(str(tmp_path / "safety.json")).load()
    assert not state.trading_halted
    assert state.reconciliation_account_id == "12"
    assert state.broker_snapshot_fingerprint == "test-fingerprint"


def test_verified_reconciliation_context_mismatch_fails_closed(tmp_path):
    manager = make_manager(tmp_path)
    verified, _ = verified_reconciliation(manager)
    wrong_attestor = BrokerContextAttestor(b"s" * 32)
    now = verified.reconciled_at
    attestation = wrong_attestor.sign(
        account_id="99",
        broker_route="paper:account:99",
        route_generation="account:99:g1",
        generation=0,
        snapshot_fingerprint="other",
        observed_at=now,
    )
    wrong_context = BrokerExecutionContext(
        account_id="99",
        broker_route="paper:account:99",
        route_generation="account:99:g1",
        generation=0,
        snapshot_fingerprint="other",
        observed_at=now,
        attestation=attestation,
    )

    result = manager.startup(
        OrderLifecycle(),
        lambda: ([], []),
        verified_reconciliation=verified,
        active_context=wrong_context,
    )
    assert not result.ready
    assert result.reason == "RECOVERY_FAILED"
    assert manager.trading_halted


def test_drift_halts_startup(tmp_path):
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 10)
    lifecycle.transition("o1", OrderStatus.FILLED, 10, 100)
    ExecutionStateStore(str(tmp_path / "execution.json")).save(lifecycle)

    manager = make_manager(tmp_path)
    result = manager.startup(OrderLifecycle(), lambda: ([], []))
    assert not result.ready
    assert result.reason == "BROKER_STATE_DRIFT"
    assert manager.trading_halted
    assert SafetyStateStore(str(tmp_path / "safety.json")).load().trading_halted


def test_broker_failure_halts_startup(tmp_path):
    manager = make_manager(tmp_path)

    def fail():
        raise ConnectionError("broker unavailable")

    result = manager.startup(OrderLifecycle(), fail)
    assert not result.ready
    assert result.reason == "RECOVERY_FAILED"
    assert manager.trading_halted


def test_persisted_halt_requires_explicit_verified_resume(tmp_path):
    manager = make_manager(tmp_path)
    ExecutionStateStore(str(tmp_path / "execution.json")).save(OrderLifecycle())
    SafetyStateStore(str(tmp_path / "safety.json")).halt("MANUAL_HALT")

    result = manager.startup(OrderLifecycle(), lambda: ([], []))
    assert not result.ready
    assert result.reason == "PERSISTED_TRADING_HALT"
    assert manager.trading_halted

    with pytest.raises(RuntimeError, match="startup reconciliation has not completed"):
        manager.resume_after_verified_reconciliation()
