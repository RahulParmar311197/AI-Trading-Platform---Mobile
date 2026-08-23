from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.historical_market_store import HistoricalMarketStore
from app.mtf_aggregator import Candle

router = APIRouter(prefix="/api/history", tags=["historical-market-data"])
store = HistoricalMarketStore()

class CandleIn(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)

class UpsertRequest(BaseModel):
    symbol: str
    timeframe: str
    candles: list[CandleIn]

@router.post("/upsert")
def upsert(payload: UpsertRequest):
    if not payload.candles:
        return {"stored": 0}
    try:
        items = [Candle(timestamp=x.timestamp, symbol=payload.symbol.upper(), timeframe=payload.timeframe, open=x.open, high=x.high, low=x.low, close=x.close, volume=x.volume) for x in payload.candles]
        return {"stored": store.upsert(items)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/{symbol}/{timeframe}")
def query(symbol: str, timeframe: str, start: datetime | None = None, end: datetime | None = None, limit: int = 5000):
    return {"candles": store.query(symbol, timeframe, start, end, limit), "count": store.count(symbol, timeframe)}
