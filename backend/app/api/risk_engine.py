from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.risk_engine import RiskLimits, evaluate

router = APIRouter(prefix="/api/risk", tags=["risk-engine"])


class RiskRequest(BaseModel):
    equity: float = Field(gt=0)
    daily_pnl: float
    proposed_risk: float = Field(ge=0)
    proposed_exposure: float = Field(ge=0)
    open_positions: int = Field(ge=0)
    recent_losses: int = Field(default=0, ge=0)
    max_risk_percent: float = Field(default=1.0, gt=0, le=10)
    max_daily_loss_percent: float = Field(default=3.0, gt=0, le=100)
    max_exposure_percent: float = Field(default=20.0, gt=0, le=100)
    max_positions: int = Field(default=5, ge=1, le=100)
    cooldown_after_loss: int = Field(default=0, ge=0, le=100)


@router.post("/evaluate")
def risk_evaluate(payload: RiskRequest):
    limits = RiskLimits(
        payload.max_risk_percent,
        payload.max_daily_loss_percent,
        payload.max_exposure_percent,
        payload.max_positions,
        payload.cooldown_after_loss,
    )
    return evaluate(
        equity=payload.equity,
        daily_pnl=payload.daily_pnl,
        proposed_risk=payload.proposed_risk,
        proposed_exposure=payload.proposed_exposure,
        open_positions=payload.open_positions,
        recent_losses=payload.recent_losses,
        limits=limits,
    ).__dict__
