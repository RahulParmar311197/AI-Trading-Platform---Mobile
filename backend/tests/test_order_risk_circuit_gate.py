from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from app.api.orders import require_trading_ready
from app.risk_circuit_observability import ObservableRiskCircuitBreaker
from app.safety_state import SafetyStateStore


def _request(tmp_path):
    app = FastAPI()
    app.state.resources = SimpleNamespace(safety_store=SafetyStateStore(str(tmp_path / "safety.json")))
    app.state.risk_circuit_breaker = ObservableRiskCircuitBreaker()
    return Request({"type": "http", "app": app}), app


def test_order_ingress_blocks_when_risk_circuit_breaker_is_engaged(tmp_path):
    request, app = _request(tmp_path)
    app.state.risk_circuit_breaker.engage("max_daily_loss")

    with pytest.raises(HTTPException) as exc:
        require_trading_ready(request)

    assert exc.value.status_code == 409
    assert exc.value.detail == {
        "code": "RISK_CIRCUIT_BREAKER_BLOCKED",
        "reason": "max_daily_loss",
    }


def test_order_ingress_allows_when_risk_circuit_breaker_is_clear(tmp_path):
    request, _ = _request(tmp_path)
    require_trading_ready(request)
