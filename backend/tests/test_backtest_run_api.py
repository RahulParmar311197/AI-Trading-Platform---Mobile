from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.backtest_run_api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_run_rejects_invalid_date_range():
    payload = {'symbol':'NIFTY','timeframe':'15m','start':'2026-01-02T00:00:00+00:00','end':'2026-01-01T00:00:00+00:00','initial_equity':100000}
    r = client.post('/api/v1/backtests/run', json=payload)
    assert r.status_code == 422

def test_run_requires_timezone():
    payload = {'symbol':'NIFTY','timeframe':'15m','start':'2026-01-01T00:00:00','end':'2026-01-02T00:00:00','initial_equity':100000}
    r = client.post('/api/v1/backtests/run', json=payload)
    assert r.status_code == 422
