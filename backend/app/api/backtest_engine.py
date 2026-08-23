from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backtest_engine import run_backtest
from app.market_data import market_data

router = APIRouter(prefix="/api/backtests", tags=["backtesting"])


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "5m"
    limit: int = Field(default=5000, ge=25, le=5000)
    starting_equity: float = Field(default=100000, gt=0)
    risk_percent: float = Field(default=1, gt=0, le=5)


@router.post("")
def backtest(payload: BacktestRequest):
    candles = market_data.candles(payload.symbol, payload.timeframe, payload.limit)
    try:
        return run_backtest(candles, payload.starting_equity, payload.risk_percent)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
