from app.portfolio_reconciliation_service import PortfolioReconciliationService
from app.safety_state import SafetyStateStore
from app.startup_recovery import StartupRecoveryCoordinator, RecoveryState
from app.startup_reconciliation_gate import StartupReconciliationGate


def test_startup_recovery_must_be_ready(tmp_path):
    recovery = StartupRecoveryCoordinator()
    gate = StartupReconciliationGate(recovery, SafetyStateStore(str(tmp_path / 'safety.json')))
    result = gate.evaluate({'NIFTY': 10}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.ready is False
    assert 'STARTUP_RECOVERY_NOT_READY' in result.reason


def test_startup_position_mismatch_halts(tmp_path):
    recovery = StartupRecoveryCoordinator()
    recovery.state = RecoveryState.READY
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    gate = StartupReconciliationGate(recovery, store)
    result = gate.evaluate({'NIFTY': 7}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.ready is False
    assert result.reason == 'PORTFOLIO_MISMATCH'
    assert store.load().trading_halted is True


def test_matching_startup_state_allows_when_no_halt(tmp_path):
    recovery = StartupRecoveryCoordinator()
    recovery.state = RecoveryState.READY
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    gate = StartupReconciliationGate(recovery, store)
    result = gate.evaluate({'NIFTY': 10}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.ready is True
