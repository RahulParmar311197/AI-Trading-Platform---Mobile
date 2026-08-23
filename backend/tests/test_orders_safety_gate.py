import pytest
from fastapi import HTTPException

from app.api.orders import require_trading_ready
from app.safety_state import SafetyStateStore


def test_order_api_rejects_persisted_halt(tmp_path, monkeypatch):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.halt("BROKER_STATE_DRIFT")
    monkeypatch.setattr("app.api.orders.SafetyStateStore", lambda: store)

    with pytest.raises(HTTPException) as exc:
        require_trading_ready()

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "TRADING_HALTED"


def test_order_api_allows_ready_state(tmp_path, monkeypatch):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.clear()
    monkeypatch.setattr("app.api.orders.SafetyStateStore", lambda: store)
    assert require_trading_ready() is None
