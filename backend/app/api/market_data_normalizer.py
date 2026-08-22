from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.market_data_normalizer import MarketDataNormalizer, GapDetector

router=APIRouter(prefix="/api/data",tags=["market-data"])
normalizer=MarketDataNormalizer(); gaps=GapDetector()
class CandleRequest(BaseModel):
    symbol:str; timeframe:str; candles:list[dict]
class NormalizeRequest(BaseModel):
    symbol:str; timeframe:str; candle:dict
class GapRequest(BaseModel):
    candles:list[dict]; expected_seconds:int=Field(gt=0)
@router.post("/normalize")
def normalize(p:NormalizeRequest):
    try:return normalizer.normalize(p.candle,p.symbol,p.timeframe).__dict__
    except ValueError as e:raise HTTPException(422,str(e))
@router.post("/gaps")
def detect(p:GapRequest):
    try:
        parsed=[normalizer.normalize(x,"UNKNOWN","UNKNOWN") for x in p.candles]
        return {"gaps":gaps.detect(parsed,p.expected_seconds)}
    except ValueError as e:raise HTTPException(422,str(e))
