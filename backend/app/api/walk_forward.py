from fastapi import APIRouter, HTTPException

from app.market_data import market_data
from app.walk_forward import walk_forward

router = APIRouter(prefix="/api/ml", tags=["ml-validation"])


@router.get("/walk-forward")
def evaluate(symbol: str, timeframe: str = "5m", limit: int = 2000, train_size: int = 500, test_size: int = 100, step: int = 100, horizon: int = 5):
    try:
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        return walk_forward(candles, train_size, test_size, step, horizon)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
