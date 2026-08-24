from app.api.ensemble import require_trading_ready
from app.safety_state import SafetyStateStore
from fastapi import HTTPException


def test_decision_execution_is_blocked_when_trading_halted(tmp_path, monkeypatch):
    store = SafetyStateStore(str(tmp_path / 'safety.json'))
    store.halt('PORTFOLIO_MISMATCH: NIFTY local=7 broker=10')
    monkeypatch.setattr('app.api.ensemble.SafetyStateStore', lambda: store)
    class Resources:
        safety_store = store
    class App:
        state = type('State', (), {'resources': Resources()})()
    request = type('Request', (), {'app': App()})()
    try:
        require_trading_ready(request)
        assert False, 'halted trading must be rejected'
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail['code'] == 'TRADING_HALTED'
