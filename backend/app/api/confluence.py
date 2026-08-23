from fastapi import APIRouter, HTTPException

from app.confluence import score
from app.market_data import market_data

router = APIRouter(prefix="/api/confluence", tags=["confluence"])


@router.get("")
def analyze(symbol: str, timeframe: str = "5m", limit: int = 500):
    candles = market_data.candles(symbol, timeframe, min(limit, 5000))
    if len(candles) < 5:
        raise HTTPException(status_code=422, detail="At least 5 candles are required")
    return score(candles)
