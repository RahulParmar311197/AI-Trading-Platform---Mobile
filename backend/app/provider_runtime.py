from __future__ import annotations
import asyncio,time
from app.data_provider import MarketDataProvider,ProviderError
from app.provider_config import ProviderConfig
class RateLimiter:
    def __init__(self,rate_per_second:float): self.interval=1.0/max(rate_per_second,0.001); self._lock=asyncio.Lock(); self._last=0.0
    async def acquire(self):
        async with self._lock:
            wait=self.interval-(time.monotonic()-self._last)
            if wait>0: await asyncio.sleep(wait)
            self._last=time.monotonic()
class ProviderRuntime:
    def __init__(self,provider:MarketDataProvider,config:ProviderConfig): self.provider=provider; self.config=config; self.limiter=RateLimiter(config.rate_limit_per_second)
    async def historical(self,symbol,start,end,timeframe):
        if not self.config.enabled: raise ProviderError(f"provider {self.provider.name} disabled")
        await self.limiter.acquire()
        try:return await asyncio.wait_for(self.provider.historical(symbol,timeframe,start,end),timeout=self.config.timeout_seconds)
        except asyncio.TimeoutError as e: raise ProviderError(f"provider {self.provider.name} timed out") from e
