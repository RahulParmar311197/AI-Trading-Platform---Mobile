from __future__ import annotations
from datetime import datetime
from app.provider_orchestrator import ProviderOrchestrator
from app.historical_market_store import HistoricalMarketStore
from app.historical_backfill import HistoricalBackfillEngine
from app.market_data import Candle
class OrchestratedBackfill:
    def __init__(self,provider_orchestrator:ProviderOrchestrator,store:HistoricalMarketStore): self.providers=provider_orchestrator; self.store=store
    async def run(self,symbol:str,timeframe:str,start:datetime,end:datetime,step_seconds:int):
        rows=await self.providers.historical(symbol,timeframe,start,end)
        candles=[Candle(timestamp=x.timestamp,symbol=symbol.upper(),timeframe=timeframe,open=x.open,high=x.high,low=x.low,close=x.close,volume=x.volume) for x in rows]
        stored=self.store.upsert(candles)
        verifier=HistoricalBackfillEngine(self.store,lambda *args: [])
        remaining=verifier.find_gaps(symbol,timeframe,start,end,step_seconds)
        return {'symbol':symbol.upper(),'timeframe':timeframe,'received':len(rows),'stored':stored,'remaining_gaps':len(remaining),'complete':not remaining}
