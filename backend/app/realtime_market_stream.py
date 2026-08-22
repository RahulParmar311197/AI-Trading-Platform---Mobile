from __future__ import annotations
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

@dataclass(frozen=True)
class MarketTick:
    symbol: str
    price: float
    volume: float = 0.0
    timestamp: datetime | None = None

class RealtimeMarketStream:
    def __init__(self, max_buffer: int = 5000):
        self.buffers=defaultdict(lambda: deque(maxlen=max_buffer)); self.subscribers=defaultdict(list); self.running=True
    async def publish(self,tick:MarketTick):
        if tick.price <= 0: raise ValueError("price must be positive")
        tick=MarketTick(tick.symbol.upper(),tick.price,tick.volume,tick.timestamp or datetime.now(timezone.utc))
        self.buffers[tick.symbol].append(tick)
        for callback in list(self.subscribers[tick.symbol]):
            result=callback(tick)
            if asyncio.iscoroutine(result): await result
    def subscribe(self,symbol:str,callback:Callable[[MarketTick],Awaitable|None]): self.subscribers[symbol.upper()].append(callback)
    def unsubscribe(self,symbol:str,callback):
        if callback in self.subscribers[symbol.upper()]: self.subscribers[symbol.upper()].remove(callback)
    def snapshot(self,symbol:str,limit:int=100): return list(self.buffers[symbol.upper()])[-limit:]
    def health(self): return {"running":self.running,"symbols":len(self.buffers),"subscriptions":sum(map(len,self.subscribers.values()))}
