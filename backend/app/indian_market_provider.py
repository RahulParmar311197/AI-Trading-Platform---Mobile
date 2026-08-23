from __future__ import annotations
import json
from datetime import datetime
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from app.data_provider import MarketDataProvider,ProviderCandle,ProviderError
from app.provider_config import ProviderConfig

class IndianMarketProvider(MarketDataProvider):
    name="indian_rest"
    def __init__(self,config:ProviderConfig): self.config=config
    async def historical(self,symbol:str,timeframe:str,start:datetime,end:datetime)->list[ProviderCandle]:
        import asyncio
        return await asyncio.to_thread(self._fetch,symbol,timeframe,start,end)
    def _fetch(self,symbol,timeframe,start,end):
        if not self.config.base_url: raise ProviderError("indian_rest BASE_URL is not configured")
        payload=json.dumps({'symbol':symbol.upper(),'timeframe':timeframe,'start':start.isoformat(),'end':end.isoformat()}).encode()
        headers={'Content-Type':'application/json'}
        if self.config.api_key: headers['Authorization']=f'Bearer {self.config.api_key}'
        req=Request(self.config.base_url,data=payload,headers=headers,method='POST')
        try:
            with urlopen(req,timeout=self.config.timeout_seconds) as response: body=json.loads(response.read().decode())
        except (HTTPError,URLError,TimeoutError) as exc: raise ProviderError(f'provider request failed: {exc}') from exc
        rows=body.get('data',body if isinstance(body,list) else [])
        result=[]
        for row in rows:
            try: result.append(ProviderCandle(datetime.fromisoformat(str(row['timestamp']).replace('Z','+00:00')),float(row['open']),float(row['high']),float(row['low']),float(row['close']),float(row.get('volume',0))))
            except (KeyError,TypeError,ValueError) as exc: raise ProviderError(f'invalid candle response: {row}') from exc
        return result
