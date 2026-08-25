from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.risk_circuit_observability import ObservableRiskCircuitBreaker


class CircuitBreakerAction(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def create_risk_circuit_router(breaker: ObservableRiskCircuitBreaker) -> APIRouter:
    router = APIRouter(prefix="/risk/circuit-breaker", tags=["risk"])

    @router.get("")
    def status() -> dict:
        state = breaker.status()
        return {"blocked": state.blocked, "reason": state.reason, "can_trade": breaker.can_trade()}

    @router.post("/engage")
    def engage(action: CircuitBreakerAction) -> dict:
        breaker.engage(action.reason)
        state = breaker.status()
        return {"blocked": state.blocked, "reason": state.reason, "can_trade": breaker.can_trade()}

    @router.post("/reset")
    def reset(action: CircuitBreakerAction) -> dict:
        if action.reason.strip().lower() != "authorized reset":
            raise HTTPException(status_code=403, detail="explicit authorized reset confirmation required")
        breaker.reset()
        state = breaker.status()
        return {"blocked": state.blocked, "reason": state.reason, "can_trade": breaker.can_trade()}

    return router
