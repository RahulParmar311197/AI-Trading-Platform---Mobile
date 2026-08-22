from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.backtest_router import router
app=FastAPI(); app.include_router(router)
class StubService:
    def __init__(self,*args,**kwargs): pass
    def run(self,*args,**kwargs): raise ValueError('symbol NIFTY is not registered on exchange BSE')
def test_invalid_symbol_exchange_returns_422(monkeypatch):
    monkeypatch.setattr('app.backtest_router.BacktestService',StubService)
    client=TestClient(app)
    r=client.post('/api/v1/backtests/run',json={'symbol':'NIFTY','timeframe':'15m','exchange':'BSE','start':'2026-01-01T09:15:00+05:30','end':'2026-01-02T15:30:00+05:30','initial_equity':100000,'risk_pct':1,'data_root':'./data'})
    assert r.status_code==422
    assert 'not registered' in r.json()['detail']
