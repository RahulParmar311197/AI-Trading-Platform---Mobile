from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from app.csv_market_data_provider import CsvMarketDataProvider
from app.data_provider import CachedProvider
from app.backtest_runner import BacktestRunner,BacktestRunRequest
class BacktestService:
    def __init__(self,data_root:str): self.provider=CachedProvider(CsvMarketDataProvider(data_root))
    def run(self,symbol:str,timeframe:str,start:datetime,end:datetime,initial_equity:float,risk_pct:float=1.0):
        result=BacktestRunner(self.provider).run(BacktestRunRequest(symbol,timeframe,start,end,initial_equity,risk_pct))
        return {'analytics':asdict(result.analytics),'equity_curve':result.equity_curve,'trade_pnls':result.trade_pnls}
