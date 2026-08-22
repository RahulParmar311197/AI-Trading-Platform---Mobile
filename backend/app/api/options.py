from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.options_engine import black_scholes, payoff

router = APIRouter(prefix="/api/options", tags=["options"])


class GreeksRequest(BaseModel):
    spot: float = Field(gt=0)
    strike: float = Field(gt=0)
    time_years: float = Field(gt=0)
    rate: float = Field(ge=-1, le=1)
    volatility: float = Field(gt=0, le=5)
    option: str = Field(pattern="^(CE|PE)$")


class PayoffRequest(BaseModel):
    spot_at_expiry: float = Field(gt=0)
    strike: float = Field(gt=0)
    premium: float = Field(ge=0)
    quantity: float = Field(gt=0)
    option: str = Field(pattern="^(CE|PE)$")
    side: str = Field(default="BUY", pattern="^(BUY|SELL)$")


@router.post("/greeks")
def greeks(payload: GreeksRequest):
    try:
        return black_scholes(**payload.model_dump()).__dict__
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/payoff")
def option_payoff(payload: PayoffRequest):
    return {"pnl": payoff(**payload.model_dump())}
