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
class CachedProvider:
    def __init__(self,provider:MarketDataProvider): self.provider=provider; self.cache={}
    async def historical(self,symbol,timeframe,start,end):
        key=(symbol,timeframe,start,end)
        if key not in self.cache:
            rows=await self.provider.historical(symbol,timeframe,start,end); seen=set(); clean=[]
            for c in sorted(rows,key=lambda x:x.timestamp):
                if c.timestamp not in seen: seen.add(c.timestamp); clean.append(c)
            self.cache[key]=clean
        return list(self.cache[key])
class PaginatedProvider:
    def __init__(self,fetch_page,page_size:int=1000,max_pages:int=100): self.fetch_page=fetch_page; self.page_size=page_size; self.max_pages=max_pages
    async def historical(self,symbol,timeframe,start,end):
        if self.page_size<1 or self.max_pages<1: raise ValueError('invalid pagination limits')
        result=[]; cursor=None
        for _ in range(self.max_pages):
            page,cursor=await self.fetch_page(symbol,timeframe,start,end,cursor,self.page_size); result.extend(page)
            if not cursor: break
        else: raise ProviderError('historical data pagination limit exceeded')
        seen=set(); clean=[]
        for c in sorted(result,key=lambda x:x.timestamp):
            if c.timestamp not in seen: seen.add(c.timestamp); clean.append(c)
        return clean
