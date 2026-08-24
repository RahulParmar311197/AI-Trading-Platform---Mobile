from fastapi import APIRouter, HTTPException, Query
import pandas as pd
from app.api.market_data import get_candles
from app.smc.engine import analyze

router = APIRouter(prefix="/api/market-data", tags=["market-evidence"])

@router.get("/evidence")
def market_evidence(symbol: str = Query("NIFTY"), timeframe: str = Query("5m"), limit: int = Query(200, ge=20, le=5000)):
    payload = get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    candles = payload["candles"]
    if len(candles) < 20:
        raise HTTPException(status_code=503, detail="insufficient market data for evidence")
    frame = pd.DataFrame(candles)
    smc = analyze(frame)
    return {
        "symbol": payload["symbol"],
        "timeframe": payload["timeframe"],
        "facts": {"latest": candles[-1], "candle_count": len(candles)},
        "technical": payload["indicators"],
        "smc": smc,
        "ict": {"status": "pending", "note": "ICT-specific evidence must be populated by the ICT analysis service; no values are invented here."},
        "data_quality": {"source": "normalized_market_data", "complete": True},
    }
