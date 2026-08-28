from datetime import datetime, timezone

from app.broker_execution_context import BrokerExecutionContext
from app.execution_authorization import ExecutionAuthorization
from app.reconciliation_result import ReconciliationResult
from app.risk_gate import RiskSnapshot
from app.safety_state import SafetyState, SafetyStateStore


def test_halt_wins_before_risk(tmp_path):
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    store.halt('PORTFOLIO_MISMATCH')
    called = []
    gate = type('Gate', (), {'authorize': lambda self, request, snapshot: called.append(1)})()
    auth = ExecutionAuthorization(store, gate, lambda request: None)
    result = auth.check(object())
    assert result.allowed is False
    assert result.code == 'TRADING_HALTED'
    assert called == []


def test_no_risk_configuration_allows_when_safe(tmp_path):
    auth = ExecutionAuthorization(SafetyStateStore(str(tmp_path / 'safety.json')))
    result = auth.check(object())
    assert result.allowed is True


def test_bound_order_requires_reconciled_account(tmp_path):
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    request = type('Request', (), {'broker_account_id': 7, 'client_order_id': 'order-1'})()
    result = ExecutionAuthorization(store).check(request)
    assert result.allowed is False
    assert result.code == 'RECONCILIATION_CONTEXT_UNAVAILABLE'


def test_bound_order_must_match_reconciled_account(tmp_path):
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    store.save(SafetyState(reconciliation_account_id='7', broker_snapshot_fingerprint='fp'))
    request = type('Request', (), {'broker_account_id': 8, 'client_order_id': 'order-1'})()
    result = ExecutionAuthorization(store).check(request)
    assert result.allowed is False
    assert result.code == 'RECONCILIATION_ACCOUNT_MISMATCH'


def test_missing_snapshot_fails_closed(tmp_path):
    gate = object()
    auth = ExecutionAuthorization(SafetyStateStore(str(tmp_path / 'safety.json')), gate, None)
    result = auth.check(object())
    assert result.allowed is False
    assert result.code == 'RISK_SNAPSHOT_UNAVAILABLE'


def test_broker_snapshot_change_fails_closed(tmp_path):
    class Gate:
        def evaluate(self, request, snapshot):
            return type('Decision', (), {'allowed': True, 'reason': 'RISK_OK'})()

    snapshots = iter([
        RiskSnapshot(broker_ready=True, broker_snapshot_fingerprint='A'),
        RiskSnapshot(broker_ready=True, broker_snapshot_fingerprint='B'),
    ])
    auth = ExecutionAuthorization(SafetyStateStore(str(tmp_path / 'safety.json')), Gate(), lambda request: next(snapshots))
    result = auth.check(object())
    assert result.allowed is False
    assert result.code == 'RISK_BROKER_SNAPSHOT_CHANGED'


def test_reconciled_snapshot_must_match_before_authorization(tmp_path):
    class Gate:
        def evaluate(self, request, snapshot):
            return type('Decision', (), {'allowed': True, 'reason': 'RISK_OK'})()

    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    store.save(SafetyState(reconciliation_account_id='7', broker_snapshot_fingerprint='OLD'))
    request = type('Request', (), {'broker_account_id': 7, 'client_order_id': 'order-1'})()
    snapshot = RiskSnapshot(broker_ready=True, broker_snapshot_fingerprint='NEW')
    auth = ExecutionAuthorization(store, Gate(), lambda request: snapshot)
    result = auth.check(request)
    assert result.allowed is False
    assert result.code == 'RECONCILIATION_SNAPSHOT_MISMATCH'


def test_authorization_returns_revalidated_snapshot(tmp_path):
    class Gate:
        def evaluate(self, request, snapshot):
            return type('Decision', (), {'allowed': True, 'reason': 'RISK_OK'})()

    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    store.save(SafetyState(reconciliation_account_id='7', broker_snapshot_fingerprint='A'))
    request = type('Request', (), {'broker_account_id': 7, 'client_order_id': 'order-1'})()
    snapshot = RiskSnapshot(broker_ready=True, broker_snapshot_fingerprint='A')
    auth = ExecutionAuthorization(store, Gate(), lambda request: snapshot)
    result = auth.check(request)
    assert result.allowed is True
    assert result.risk_snapshot is snapshot
