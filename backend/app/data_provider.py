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
