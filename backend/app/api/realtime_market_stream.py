from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from app.realtime_market_stream import RealtimeMarketStream, MarketTick

router=APIRouter(prefix="/api/realtime",tags=["realtime-market"]); stream=RealtimeMarketStream()
class TickRequest(BaseModel): symbol:str; price:float=Field(gt=0); volume:float=Field(default=0,ge=0)
@router.get("/health")
def health(): return stream.health()
@router.get("/{symbol}/snapshot")
def snapshot(symbol:str,limit:int=100): return [x.__dict__ for x in stream.snapshot(symbol,limit)]
@router.post("/publish")
async def publish(p:TickRequest):
    await stream.publish(MarketTick(p.symbol,p.price,p.volume)); return {"status":"published","symbol":p.symbol.upper()}
@router.websocket("/ws/{symbol}")
async def websocket(ws:WebSocket,symbol:str):
    await ws.accept(); queue=[]
    async def callback(tick): queue.append(tick)
    stream.subscribe(symbol,callback)
    try:
        while True:
            if queue:
                tick=queue.pop(0); await ws.send_json({"symbol":tick.symbol,"price":tick.price,"volume":tick.volume,"timestamp":tick.timestamp.isoformat()})
            else: await ws.receive_text()
    except WebSocketDisconnect: pass
    finally: stream.unsubscribe(symbol,callback)
