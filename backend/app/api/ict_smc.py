from fastapi import APIRouter, HTTPException
from app.market_data import market_data
from app.ict_smc import analyze

router = APIRouter(prefix="/api/ict", tags=["ict-smc"])

@router.get("/analysis")
def analysis(symbol: str, timeframe: str = "5m", limit: int = 300):
    try:
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        return {"symbol": symbol.upper(), "timeframe": timeframe, **analyze(candles)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
