from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.market_data import market_data
from app.strategy_backtest import BacktestConfig, run_strategy_backtest

router = APIRouter(prefix="/api/backtest", tags=["strategy-backtest"])

class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "5m"
    limit: int = Field(default=2000, ge=40, le=5000)
    initial_capital: float = Field(default=100000, gt=0)
    risk_per_trade: float = Field(default=0.01, gt=0, le=0.1)
    fee_bps: float = Field(default=3, ge=0)
    slippage_bps: float = Field(default=1, ge=0)
    min_confidence: float = Field(default=0.35, ge=0, le=1)

@router.post("/strategy")
def strategy_backtest(payload: BacktestRequest):
    try:
        candles = market_data.candles(payload.symbol, payload.timeframe, payload.limit)
        config = BacktestConfig(**{k: v for k, v in payload.model_dump().items() if k not in {"symbol", "timeframe", "limit"}})
        return {"symbol": payload.symbol.upper(), "timeframe": payload.timeframe, **run_strategy_backtest(candles, config)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
