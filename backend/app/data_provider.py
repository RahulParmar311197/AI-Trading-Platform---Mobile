from __future__ import annotations
from abc import ABC,abstractmethod
from datetime import datetime
from dataclasses import dataclass
class ProviderError(RuntimeError):pass
@dataclass(frozen=True)
class ProviderCandle:
    timestamp:datetime; open:float; high:float; low:float; close:float; volume:float
class MarketDataProvider(ABC):
    name='base'
    def __init__(self,config=None):self.config=config
    @abstractmethod
    async def historical(self,symbol:str,timeframe:str,start:datetime,end:datetime)->list[ProviderCandle]:...
class ProviderRegistry:
    def __init__(self): self._providers={}
    def register(self,provider:MarketDataProvider):
        if provider.name in self._providers: raise ValueError(f'provider already registered: {provider.name}')
        self._providers[provider.name]=provider
    def get(self,name:str):
        if name not in self._providers: raise KeyError(f'provider not registered: {name}')
        return self._providers[name]
    def names(self): return tuple(self._providers.keys())
