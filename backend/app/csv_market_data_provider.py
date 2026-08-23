from __future__ import annotations
import csv
from datetime import datetime, timezone
from pathlib import Path
from app.data_provider import MarketDataProvider,ProviderCandle

class CsvMarketDataProvider(MarketDataProvider):
    name='csv'
    def __init__(self,root:str|Path): self.root=Path(root)
    async def historical(self,symbol:str,timeframe:str,start:datetime,end:datetime)->list[ProviderCandle]:
        path=self.root/f'{symbol}_{timeframe}.csv'
        if not path.exists(): raise FileNotFoundError(str(path))
        rows=[]
        with path.open(newline='',encoding='utf-8') as f:
            for row in csv.DictReader(f):
                ts=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
                if ts.tzinfo is None: ts=ts.replace(tzinfo=timezone.utc)
                if start<=ts<end: rows.append(ProviderCandle(ts,float(row['open']),float(row['high']),float(row['low']),float(row['close']),float(row.get('volume',0))))
        rows.sort(key=lambda x:x.timestamp)
        return rows
