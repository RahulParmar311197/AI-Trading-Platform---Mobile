from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.market_data import market_data
from app.unified_backtest import UnifiedBacktestConfig, run

router = APIRouter(prefix="/api/backtest", tags=["unified-backtest"])

class UnifiedRequest(BaseModel):
    symbol: str
    timeframes: str = "1h,15m,5m"
    execution_tf: str = "5m"
    limit: int = Field(1000, ge=30, le=5000)
    initial_capital: float = Field(100000, gt=0)
    risk_per_trade: float = Field(0.01, gt=0, le=0.1)
    fee_bps: float = Field(3, ge=0)
    slippage_bps: float = Field(1, ge=0)
    min_confidence: float = Field(0.35, ge=0, le=1)

@router.post("/unified")
def unified_backtest(payload: UnifiedRequest):
    try:
        frames={tf.strip(): market_data.candles(payload.symbol, tf.strip(), payload.limit) for tf in payload.timeframes.split(",") if tf.strip()}
        cfg=UnifiedBacktestConfig(initial_capital=payload.initial_capital,risk_per_trade=payload.risk_per_trade,fee_bps=payload.fee_bps,slippage_bps=payload.slippage_bps,min_confidence=payload.min_confidence)
        return {"symbol":payload.symbol.upper(),"execution_tf":payload.execution_tf,**run(frames,payload.execution_tf,cfg)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
