from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.trade_risk import RiskConfig, check_trade

router = APIRouter(prefix="/api/risk", tags=["risk"])

class RiskRequest(BaseModel):
    equity: float = Field(gt=0)
    day_start_equity: float = Field(gt=0)
    peak_equity: float = Field(gt=0)
    open_positions: int = Field(ge=0)
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    existing_exposure: float = Field(default=0, ge=0)
    max_daily_loss_pct: float = Field(default=0.02, gt=0, le=1)
    max_drawdown_pct: float = Field(default=0.10, gt=0, le=1)
    max_open_positions: int = Field(default=3, ge=1)
    max_position_risk_pct: float = Field(default=0.01, gt=0, le=0.1)
    max_gross_exposure_pct: float = Field(default=1.0, gt=0, le=2)
    max_single_position_pct: float = Field(default=0.25, gt=0, le=1)

@router.post("/check")
def risk_check(p: RiskRequest):
    cfg = RiskConfig(p.max_daily_loss_pct,p.max_drawdown_pct,p.max_open_positions,p.max_position_risk_pct,p.max_gross_exposure_pct,p.max_single_position_pct)
    return check_trade(equity=p.equity, day_start_equity=p.day_start_equity, peak_equity=p.peak_equity, open_positions=p.open_positions, entry=p.entry, stop=p.stop, existing_exposure=p.existing_exposure, config=cfg).__dict__
