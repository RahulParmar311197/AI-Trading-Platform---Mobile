from fastapi import APIRouter, HTTPException

from app.market_data import market_data
from app.ml_training import baseline_metrics, chronological_split, make_dataset

router = APIRouter(prefix="/api/ml", tags=["ml-training"])


@router.get("/dataset")
def dataset_info(symbol: str, timeframe: str = "5m", limit: int = 1000, horizon: int = 5):
    try:
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        examples = make_dataset(candles, horizon)
        train, validation, test = chronological_split(examples)
        return {
            "symbol": symbol.upper(), "timeframe": timeframe,
            "samples": len(examples),
            "splits": {"train": len(train), "validation": len(validation), "test": len(test)},
            "train_metrics": baseline_metrics(train),
            "validation_metrics": baseline_metrics(validation),
            "test_metrics": baseline_metrics(test),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
