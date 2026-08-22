from __future__ import annotations
from datetime import datetime
from app.data_provider import MarketDataProvider
from app.provider_config import ProviderConfig
from app.provider_runtime import ProviderRuntime
from app.provider_failover import ProviderFailover
class ProviderOrchestrator:
    def __init__(self,providers:list[MarketDataProvider],configs:dict[str,ProviderConfig]|None=None):
        configs=configs or {}; runtimes=[]
        for provider in providers:
            cfg=configs.get(provider.name) or getattr(provider,'config',None) or ProviderConfig.from_env(provider.name)
            provider.config=cfg; runtimes.append(ProviderRuntime(provider,cfg))
        self.failover=ProviderFailover(runtimes)
    async def historical(self,symbol:str,timeframe:str,start:datetime,end:datetime): return await self.failover.historical(symbol,start,end,timeframe)
