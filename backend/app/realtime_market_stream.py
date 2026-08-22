from __future__ import annotations
import asyncio
from collections import defaultdict,deque
from dataclasses import dataclass
from datetime import datetime,timezone
from typing import Awaitable,Callable
@dataclass(frozen=True)
class MarketTick:
    symbol:str; price:float; volume:float=0.0; timestamp:datetime|None=None
class RealtimeMarketStream:
    def __init__(self,max_buffer:int=5000):
        if max_buffer<1:raise ValueError('max_buffer must be positive')
        self.buffers=defaultdict(lambda:deque(maxlen=max_buffer)); self.subscribers=defaultdict(list); self.running=True
    @staticmethod
    def _normalize(tick:MarketTick)->MarketTick:
        if tick.price<=0:raise ValueError('price must be positive')
        ts=tick.timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:ts=ts.replace(tzinfo=timezone.utc)
        else:ts=ts.astimezone(timezone.utc)
        return MarketTick(tick.symbol.upper(),tick.price,max(0.0,tick.volume),ts)
    async def publish(self,tick:MarketTick):
        tick=self._normalize(tick); self.buffers[tick.symbol].append(tick)
        callbacks=list(self.subscribers[tick.symbol])
        results=await asyncio.gather(*(cb(tick) for cb in callbacks),return_exceptions=True)
        errors=[r for r in results if isinstance(r,Exception)]
        if errors:raise errors[0]
    def subscribe(self,symbol:str,callback:Callable[[MarketTick],Awaitable|None]):
        symbol=symbol.upper()
        if callback not in self.subscribers[symbol]:self.subscribers[symbol].append(callback)
    def unsubscribe(self,symbol:str,callback):
        symbol=symbol.upper()
        if callback in self.subscribers[symbol]:self.subscribers[symbol].remove(callback)
    def snapshot(self,symbol:str,limit:int=100):
        if limit<1:return []
        return list(self.buffers[symbol.upper()])[-limit:]
    def health(self):return {'running':self.running,'symbols':len(self.buffers),'subscriptions':sum(map(len,self.subscribers.values()))}
