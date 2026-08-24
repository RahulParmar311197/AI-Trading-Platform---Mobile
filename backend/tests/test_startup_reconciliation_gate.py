from app.safety_state import SafetyStateStore
from app.startup_recovery import StartupRecoveryCoordinator, RecoveryState
from app.startup_reconciliation_gate import StartupReconciliationGate


def _ready_gate(tmp_path):
    recovery = StartupRecoveryCoordinator()
    recovery.state = RecoveryState.READY
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    return StartupReconciliationGate(recovery, store), store


def test_startup_recovery_must_be_ready(tmp_path):
    recovery = StartupRecoveryCoordinator()
    gate = StartupReconciliationGate(recovery, SafetyStateStore(str(tmp_path / 'safety.json')))
    result = gate.evaluate({'NIFTY': 10}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.ready is False
    assert 'STARTUP_RECOVERY_NOT_READY' in result.reason


def test_startup_position_mismatch_halts(tmp_path):
    gate, store = _ready_gate(tmp_path)
    result = gate.evaluate({'NIFTY': 7}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.ready is False
    assert result.reason == 'PORTFOLIO_MISMATCH'
    state = store.load()
    assert state.trading_halted is True
    assert 'PORTFOLIO_MISMATCH' in (state.halt_reason or '')


def test_malformed_broker_position_halts(tmp_path):
    gate, store = _ready_gate(tmp_path)
    result = gate.evaluate({}, [{'symbol': 'NIFTY'}])
    assert result.ready is False
    assert result.reason == 'PORTFOLIO_RECONCILIATION_INVALID'
    assert store.load().trading_halted is True
    assert 'quantity missing' in (store.load().halt_reason or '')


def test_persisted_halt_blocks_matching_positions(tmp_path):
    gate, store = _ready_gate(tmp_path)
    first = gate.evaluate({'NIFTY': 7}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert first.ready is False
    second = gate.evaluate({'NIFTY': 10}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert second.ready is False
    assert second.reason.startswith('SAFETY_HALT_ACTIVE:')


def test_matching_startup_state_allows_when_no_halt(tmp_path):
    gate, store = _ready_gate(tmp_path)
    result = gate.evaluate({'NIFTY': 10}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.ready is True
    assert store.load().trading_halted is False
