from app.portfolio_reconciliation_guard import PortfolioReconciliationGuard
from app.safety_state import SafetyStateStore


def test_mismatch_persists_trading_halt(tmp_path):
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    guard = PortfolioReconciliationGuard(store)
    result = guard.reconcile({'NIFTY': 7}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.matched is False
    assert store.load().trading_halted is True
    try:
        guard.assert_trading_allowed()
        assert False, 'trading must remain halted'
    except RuntimeError as exc:
        assert 'TRADING_HALTED' in str(exc)


def test_matching_reconciliation_clears_reconciliation_halt(tmp_path):
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    guard = PortfolioReconciliationGuard(store)
    guard.reconcile({'NIFTY': 7}, [{'symbol': 'NIFTY', 'quantity': 10}])
    result = guard.reconcile({'NIFTY': 10}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.matched is True
    assert store.load().trading_halted is False


def test_unrelated_manual_halt_is_not_auto_cleared(tmp_path):
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    store.halt('MANUAL_OPERATOR_HALT')
    guard = PortfolioReconciliationGuard(store)
    guard.reconcile({'NIFTY': 10}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert store.load().trading_halted is True
    assert store.load().halt_reason == 'MANUAL_OPERATOR_HALT'
