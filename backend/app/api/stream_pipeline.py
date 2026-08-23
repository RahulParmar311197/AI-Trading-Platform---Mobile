from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.api.realtime_market_stream import stream
from app.stream_candle_pipeline import StreamCandlePipeline
router=APIRouter(prefix="/api/pipeline",tags=["stream-pipeline"])
pipeline=StreamCandlePipeline(stream)
class SubscribeRequest(BaseModel): symbols:list[str]; timeframes:list[str]
class PublishRequest(BaseModel): symbol:str; price:float=Field(gt=0); volume:float=Field(default=0,ge=0)
@router.post("/subscribe")
def subscribe(p:SubscribeRequest): pipeline.subscribe_symbols(p.symbols,p.timeframes); return {"status":"subscribed","symbols":p.symbols,"timeframes":p.timeframes}
@router.post("/publish")
async def publish(p:PublishRequest): await pipeline.publish(p.symbol,p.price,p.volume); return {"status":"published"}
@router.post("/flush")
def flush(): return {"candles":[c.__dict__ for c in pipeline.flush()]}
