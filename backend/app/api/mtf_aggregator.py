from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from app.mtf_aggregator import Candle, MultiTimeframeAggregator
router=APIRouter(prefix="/api/mtf",tags=["multi-timeframe"]); engine=MultiTimeframeAggregator()
class AggregateRequest(BaseModel):
    symbol:str; source_timeframe:str; target_timeframe:str; candles:list[dict]
class AlignmentRequest(BaseModel):
    timeframe:str; candles:list[dict]
def parse(items,symbol,timeframe): return [Candle(datetime.fromisoformat(x["timestamp"].replace("Z","+00:00")),float(x["open"]),float(x["high"]),float(x["low"]),float(x["close"]),float(x["volume"]),symbol.upper(),timeframe) for x in items]
@router.post("/aggregate")
def aggregate(p:AggregateRequest):
    try:return [x.__dict__ for x in engine.aggregate(parse(p.candles,p.symbol,p.source_timeframe),p.target_timeframe)]
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@router.post("/alignment")
def alignment(p:AlignmentRequest):
    try:return {"issues":engine.validate_alignment(parse(p.candles,"UNKNOWN",p.timeframe),p.timeframe)}
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
