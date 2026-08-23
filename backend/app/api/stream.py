import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["stream"])

@router.websocket("/ws/market/{symbol}")
async def market_stream(websocket: WebSocket, symbol: str):
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(json.dumps({"type": "heartbeat", "symbol": symbol}))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
