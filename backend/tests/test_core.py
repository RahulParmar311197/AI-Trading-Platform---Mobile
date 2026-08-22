import pandas as pd
from app.smc.engine import analyze
from app.risk.engine import RiskEngine
from app.schemas import OrderRequest, RiskConfig
from app.backtest.engine import run

def candles():
    return pd.DataFrame([
        {"open":100,"high":102,"low":99,"close":101,"volume":100},
        {"open":101,"high":103,"low":100,"close":102,"volume":100},
        {"open":102,"high":105,"low":101,"close":104,"volume":100},
        {"open":104,"high":108,"low":103,"close":107,"volume":100},
        {"open":107,"high":110,"low":106,"close":109,"volume":100},
        {"open":109,"high":112,"low":108,"close":111,"volume":100},
    ])

def test_smc_returns_structured_analysis():
    result=analyze(candles(),1)
    assert "bias" in result and "score" in result

def test_risk_vetoes_stale_market():
    order=OrderRequest(symbol="NIFTY",side="BUY",quantity=1)
    result=RiskEngine().validate(order,RiskConfig(),100000,0,0,0,market_fresh=False)
    assert not result.approved and "MARKET_DATA_STALE" in result.reasons

def test_backtest_returns_metrics():
    result=run(candles(),100000,0.005)
    assert set(["net_profit","trades","win_rate"]).issubset(result)
