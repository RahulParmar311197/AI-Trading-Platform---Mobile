from __future__ import annotations
from datetime import datetime
from app.realtime_market_stream import RealtimeMarketStream, MarketTick
from app.candle_builder import CandleBuilder, LiveCandle

class StreamCandlePipeline:
    def __init__(self, stream: RealtimeMarketStream, on_candle_close=None):
        self.stream=stream; self.on_candle_close=on_candle_close; self.builder=CandleBuilder(on_close=self._closed)
    def _closed(self,candle:LiveCandle):
        if self.on_candle_close: self.on_candle_close(candle)
    def subscribe_symbols(self,symbols:list[str],timeframes:list[str]):
        for symbol in symbols:
            for timeframe in timeframes: self.stream.subscribe(symbol,self._callback_factory(timeframe))
    def _callback_factory(self,timeframe):
        async def callback(tick:MarketTick): self.builder.update_tick(tick.symbol,timeframe,tick.timestamp,tick.price,tick.volume)
        return callback
    async def publish(self,symbol:str,price:float,volume:float=0,timestamp:datetime|None=None): await self.stream.publish(MarketTick(symbol,price,volume,timestamp))
    def flush(self): return self.builder.flush()
