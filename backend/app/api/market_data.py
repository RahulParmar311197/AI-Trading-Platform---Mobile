from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.indicators import atr, ema, sma, volatility
from app.market_data import Candle, market_data

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


class CandleIn(BaseModel):
    timestamp: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(default=0, ge=0)


@router.post("/candles", status_code=202)
def ingest_candle(payload: CandleIn):
    from datetime import datetime
    market_data.put(Candle(timestamp=datetime.fromisoformat(payload.timestamp), **payload.model_dump(exclude={"timestamp"})))
    return {"accepted": True}


@router.get("/candles")
def get_candles(symbol: str, timeframe: str = "5m", limit: int = 200):
    candles = market_data.candles(symbol, timeframe, min(limit, 5000))
    closes = [x.close for x in candles]
    highs = [x.high for x in candles]
    lows = [x.low for x in candles]
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candles": [x.__dict__ for x in candles],
        "indicators": {
            "sma20": sma(closes, 20),
            "ema20": ema(closes, 20),
            "atr14": atr(highs, lows, closes, 14),
            "volatility20": volatility(closes, 20),
        },
    }
