from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.market_data import market_data
from app.position_sizing import size_position
from app.strategy import generate_signal

router = APIRouter(prefix="/api/signals", tags=["signals"])


class SizeRequest(BaseModel):
    equity: float = Field(gt=0)
    risk_percent: float = Field(gt=0, le=5)
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    max_quantity: float | None = Field(default=None, gt=0)


@router.get("")
def signal(symbol: str, timeframe: str = "5m", limit: int = 500):
    candles = market_data.candles(symbol, timeframe, min(limit, 5000))
    result = generate_signal(candles)
    if result is None:
        return {"signal": None, "symbol": symbol.upper(), "timeframe": timeframe}
    return {"signal": result.__dict__, "symbol": symbol.upper(), "timeframe": timeframe}


@router.post("/position-size")
def position_size(payload: SizeRequest):
    try:
        return size_position(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
