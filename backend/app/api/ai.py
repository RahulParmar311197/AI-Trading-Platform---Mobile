from fastapi import APIRouter, HTTPException

from app.ai_model import predict
from app.market_data import market_data

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/prediction")
def prediction(symbol: str, timeframe: str = "5m", limit: int = 200):
    try:
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        result = predict(candles)
        return {"symbol": symbol.upper(), "timeframe": timeframe, **result.__dict__}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
