from fastapi import APIRouter, HTTPException
from app.market_data import market_data
from app.ensemble_v2 import decide_v2

router = APIRouter(prefix="/api/decision", tags=["ensemble-v2"])

@router.get("/v2")
def decision(symbol: str, timeframe: str = "5m", limit: int = 300):
    try:
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        return {"symbol": symbol.upper(), "timeframe": timeframe, **decide_v2(candles).__dict__}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
