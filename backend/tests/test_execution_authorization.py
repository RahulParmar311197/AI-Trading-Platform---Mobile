from app.execution_authorization import ExecutionAuthorization
from app.safety_state import SafetyStateStore


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


def test_missing_snapshot_fails_closed(tmp_path):
    gate = object()
    auth = ExecutionAuthorization(SafetyStateStore(str(tmp_path / 'safety.json')), gate, None)
    result = auth.check(object())
    assert result.allowed is False
    assert result.code == 'RISK_SNAPSHOT_UNAVAILABLE'
