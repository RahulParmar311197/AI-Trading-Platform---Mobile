from fastapi import APIRouter, HTTPException
from app.market_data import market_data
from app.mtf_analysis import multi_timeframe_analysis

router = APIRouter(prefix="/api/mtf", tags=["multi-timeframe"])

@router.get("/analysis")
def analysis(symbol: str, timeframes: str = "1h,15m,5m", limit: int = 300):
    try:
        frames = {tf.strip(): market_data.candles(symbol, tf.strip(), min(limit, 5000)) for tf in timeframes.split(",") if tf.strip()}
        return {"symbol": symbol.upper(), **multi_timeframe_analysis(frames)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
