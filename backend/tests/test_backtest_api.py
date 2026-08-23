from fastapi.testclient import TestClient
from app.backtest_api import router
from fastapi import FastAPI
app=FastAPI(); app.include_router(router)
client=TestClient(app)

def test_analytics_endpoint():
 r=client.post('/api/v1/backtests/analytics',json={'initial_equity':100000,'equity_curve':[100000,101000,99000,102000],'trade_pnls':[1000,-2000,3000]}); assert r.status_code==200; assert r.json()['trades']==3

def test_validation_error():
 r=client.post('/api/v1/backtests/analytics',json={'initial_equity':0,'equity_curve':[100]}); assert r.status_code==422
