from fastapi import APIRouter, HTTPException
from app.market_data import market_data
from app.mtf_ensemble import decide_mtf

router = APIRouter(prefix="/api/decision", tags=["mtf-ensemble"])

@router.get("/mtf")
def mtf_decision(symbol: str, timeframes: str = "1d,4h,1h,15m,5m", limit: int = 300):
    try:
        frames = {tf.strip(): market_data.candles(symbol, tf.strip(), min(limit, 5000)) for tf in timeframes.split(",") if tf.strip()}
        return {"symbol": symbol.upper(), **decide_mtf(frames)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
