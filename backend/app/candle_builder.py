from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
TIMEFRAME_SECONDS={"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"4h":14400,"1d":86400}
@dataclass
class LiveCandle:
    symbol:str; timeframe:str; start:datetime; open:float; high:float; low:float; close:float; volume:float=0.0; ticks:int=0
    def update(self,price:float,volume:float=0.0):
        if price<=0: raise ValueError("price must be positive")
        self.high=max(self.high,price); self.low=min(self.low,price); self.close=price; self.volume+=max(0.0,volume); self.ticks+=1
def bucket(ts:datetime,timeframe:str)->datetime:
    seconds=TIMEFRAME_SECONDS[timeframe]; epoch=int(ts.timestamp()); return datetime.fromtimestamp(epoch-epoch%seconds,tz=ts.tzinfo)
class CandleBuilder:
    def __init__(self,on_close:Callable[[LiveCandle],None]|None=None): self.active={}; self.on_close=on_close
    def update_tick(self,symbol:str,timeframe:str,timestamp:datetime,price:float,volume:float=0.0):
        if timeframe not in TIMEFRAME_SECONDS: raise ValueError("unsupported timeframe")
        key=(symbol.upper(),timeframe); start=bucket(timestamp,timeframe); current=self.active.get(key); closed=None
        if current and current.start!=start:
            closed=current; self.active.pop(key,None)
            if self.on_close: self.on_close(closed)
        if current is None or current.start!=start:
            current=LiveCandle(symbol.upper(),timeframe,start,price,price,price,price,max(0.0,volume),1); self.active[key]=current
        else: current.update(price,volume)
        return {"closed":closed,"current":current}
    def flush(self):
        items=list(self.active.values()); self.active.clear()
        if self.on_close:
            for candle in items:self.on_close(candle)
        return items
