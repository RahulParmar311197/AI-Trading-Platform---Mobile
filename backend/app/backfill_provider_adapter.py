from __future__ import annotations
from datetime import datetime,timedelta
from app.data_provider import MarketDataProvider
from app.provider_runtime import ProviderRuntime
from app.historical_market_store import HistoricalMarketStore
from app.market_data import Candle
TIMEFRAME_SECONDS={'1m':60,'3m':180,'5m':300,'15m':900,'30m':1800,'1h':3600,'4h':14400,'1d':86400}
class ProviderBackfillAdapter:
    def __init__(self,provider:MarketDataProvider,store:HistoricalMarketStore,chunk_seconds:int=86400):
        self.runtime=ProviderRuntime(provider,provider.config if hasattr(provider,'config') else None); self.store=store; self.chunk_seconds=chunk_seconds
    async def run(self,symbol:str,timeframe:str,start:datetime,end:datetime):
        if timeframe not in TIMEFRAME_SECONDS: raise ValueError(f'unsupported timeframe: {timeframe}')
        step=TIMEFRAME_SECONDS[timeframe]; cursor=start; total=0; chunks=0
        while cursor<=end:
            chunk_end=min(end,cursor+timedelta(seconds=self.chunk_seconds-step))
            rows=await self.runtime.historical(symbol,cursor,chunk_end,timeframe)
            candles=[Candle(timestamp=x.timestamp,symbol=symbol.upper(),timeframe=timeframe,open=x.open,high=x.high,low=x.low,close=x.close,volume=x.volume) for x in rows]
            total+=self.store.upsert(candles)
            chunks+=1; cursor=chunk_end+timedelta(seconds=step)
        return {'symbol':symbol.upper(),'timeframe':timeframe,'chunks':chunks,'stored':total}
