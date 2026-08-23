from __future__ import annotations
from datetime import datetime
import json
from urllib.request import Request,urlopen
from app.data_provider import MarketDataProvider,ProviderCandle,ProviderError
class IndianMarketProvider(MarketDataProvider):
    name='indian_rest'
    def __init__(self,config): super().__init__(config)
    async def historical(self,symbol:str,timeframe:str,start:datetime,end:datetime)->list[ProviderCandle]:
        if not self.config or not self.config.base_url: raise ProviderError('indian_rest BASE_URL is not configured')
        if start>end: raise ProviderError('start must be before end')
        url=self.config.base_url.rstrip('/')+'/historical'
        payload=json.dumps({'symbol':symbol.upper(),'timeframe':timeframe,'start':start.isoformat(),'end':end.isoformat()}).encode()
        headers={'Content-Type':'application/json'}
        if self.config.api_key: headers['Authorization']='Bearer '+self.config.api_key
        req=Request(url,data=payload,headers=headers,method='POST')
        try:
            with urlopen(req,timeout=self.config.timeout_seconds) as response: body=json.loads(response.read().decode())
        except Exception as exc: raise ProviderError(f'indian_rest request failed: {exc}') from exc
        items=body.get('candles',body) if isinstance(body,(dict,list)) else []
        if not isinstance(items,list): raise ProviderError('invalid historical response: candles must be a list')
        result=[]
        for row in items:
            try:
                result.append(ProviderCandle(timestamp=datetime.fromisoformat(str(row['timestamp']).replace('Z','+00:00')),open=float(row['open']),high=float(row['high']),low=float(row['low']),close=float(row['close']),volume=float(row.get('volume',0))))
            except (KeyError,TypeError,ValueError) as exc: raise ProviderError(f'invalid candle payload: {row}') from exc
        return result
