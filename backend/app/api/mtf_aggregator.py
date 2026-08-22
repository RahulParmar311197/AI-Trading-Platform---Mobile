from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.mtf_aggregator import Candle, aggregate

router = APIRouter(prefix="/api/mtf", tags=["mtf-aggregator"])

class CandleIn(BaseModel):
    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)

class AggregateRequest(BaseModel):
    candles: list[CandleIn]
    target_timeframe: str

@router.post("/aggregate")
def aggregate_candles(payload: AggregateRequest):
    if not payload.candles:
        return {"candles": [], "count": 0}
    try:
        source = [Candle(**c.model_dump()) for c in payload.candles]
        result = aggregate(source, payload.target_timeframe)
        return {"candles": [c.__dict__ for c in result], "count": len(result)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
