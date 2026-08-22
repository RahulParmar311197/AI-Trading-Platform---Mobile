from fastapi import APIRouter, HTTPException
from app.market_data import market_data
from app.ml_training import make_dataset, chronological_split
from app.ml_trainer import train
from app.model_registry import registry

router = APIRouter(prefix="/api/ml", tags=["ml-training"])

@router.post("/train")
def train_model(symbol: str, timeframe: str = "5m", limit: int = 2000, horizon: int = 5, version: str = "baseline-1"):
    try:
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        examples = make_dataset(candles, horizon)
        train_set, validation_set, test_set = chronological_split(examples)
        result = train(train_set, validation_set)
        model = result["model"]
        test_probabilities = model.predict_proba([x.features for x in test_set])
        from app.ml_metrics import classification_metrics
        test_metrics = classification_metrics([x.label for x in test_set], test_probabilities)
        metrics = {"validation": result["metrics"], "test": test_metrics, "samples": {"train": len(train_set), "validation": len(validation_set), "test": len(test_set)}}
        registered = registry.register(f"{symbol.upper()}_{timeframe}", version, metrics)
        return {"model": registered.__dict__, "training": metrics}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
