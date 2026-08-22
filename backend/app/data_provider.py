from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import asyncio
@dataclass(frozen=True)
class ProviderCandle:
    timestamp: datetime; open: float; high: float; low: float; close: float; volume: float
class MarketDataProvider(ABC):
    name: str
    @abstractmethod
    async def historical(self,symbol:str,timeframe:str,start:datetime,end:datetime)->list[ProviderCandle]: ...
class ProviderError(RuntimeError): pass
class RetryPolicy:
    def __init__(self,max_attempts:int=3,base_delay:float=0.5,max_delay:float=8.0): self.max_attempts=max_attempts; self.base_delay=base_delay; self.max_delay=max_delay
    async def run(self,fn):
        last=None
        for attempt in range(self.max_attempts):
            try:return await fn()
            except Exception as exc:
                last=exc
                if attempt+1<self.max_attempts: await asyncio.sleep(min(self.max_delay,self.base_delay*(2**attempt)))
        raise ProviderError(str(last)) from last
class ProviderRegistry:
    def __init__(self): self._providers={}
    def register(self,provider:MarketDataProvider): self._providers[provider.name]=provider
    def get(self,name:str)->MarketDataProvider:
        if name not in self._providers: raise KeyError(f"unknown provider: {name}")
        return self._providers[name]
    def names(self): return sorted(self._providers)
