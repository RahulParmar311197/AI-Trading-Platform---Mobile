from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from app.csv_market_data_provider import CsvMarketDataProvider
from app.data_provider import CachedProvider
from app.backtest_runner import BacktestRunner,BacktestRunRequest
from app.symbol_registry import SymbolRegistry
from app.symbol_config import load_symbol_registry
class BacktestService:
 def __init__(self,data_root:str,symbol_registry:SymbolRegistry|None=None,symbol_catalog:str|None=None):
  self.provider=CachedProvider(CsvMarketDataProvider(data_root))
  catalog=Path(symbol_catalog) if symbol_catalog else Path(__file__).resolve().parents[1]/'config'/'symbols.json'
  self.symbol_registry=symbol_registry or load_symbol_registry(catalog)
 def run(self,symbol:str,timeframe:str,start:datetime,end:datetime,initial_equity:float,risk_pct:float=1.0,exchange:str='NSE'):
  self.symbol_registry.validate(symbol,exchange)
  result=BacktestRunner(self.provider).run(BacktestRunRequest(symbol,timeframe,start,end,initial_equity,risk_pct,exchange))
  return {'analytics':asdict(result.analytics),'equity_curve':result.equity_curve,'trade_pnls':result.trade_pnls}
