from __future__ import annotations
from dataclasses import dataclass
from app.historical_data_loader import HistoricalDataLoader,HistoricalDataRequest
from app.backtest_analytics import BacktestAnalytics,BacktestAnalyticsEngine
from app.ai_decision import AIDecisionEngine
from app.risk_position_sizing import RiskPositionSizer
from app.trade_plan import TradeAction,TradePlanValidator
from app.paper_portfolio import PaperPortfolio
@dataclass(frozen=True)
class BacktestRunRequest:
    symbol:str; timeframe:str; start:object; end:object; initial_equity:float; risk_pct:float=1.0
@dataclass(frozen=True)
class BacktestRunResult:
    analytics:BacktestAnalytics; equity_curve:list[float]; trade_pnls:list[float]
class BacktestRunner:
    def __init__(self,data_provider): self.loader=HistoricalDataLoader(data_provider)
    def run(self,req:BacktestRunRequest)->BacktestRunResult:
        candles=self.loader.load(HistoricalDataRequest(req.symbol,req.timeframe,req.start,req.end)); portfolio=PaperPortfolio(req.initial_equity); equity=[req.initial_equity]
        for i in range(60,len(candles)):
            price=candles[i].close; portfolio.update({req.symbol:price}); window=candles[:i+1]; d=AIDecisionEngine().decide(window)
            if d.tradeable:
                entry=price; atr=max(c.high-c.low for c in window[-14:]); stop=entry-atr if d.action=='BUY' else entry+atr; target=entry+2*atr if d.action=='BUY' else entry-2*atr; sized=RiskPositionSizer(req.risk_pct).size(req.initial_equity,entry,stop)
                if sized.valid:
                    try: portfolio.open(TradePlanValidator().build(req.symbol,TradeAction.BUY if d.action=='BUY' else TradeAction.SELL,entry,stop,target,sized.quantity,sized.risk_amount))
                    except ValueError: pass
            equity.append(portfolio.equity({req.symbol:price}))
        if candles: portfolio.update({req.symbol:candles[-1].close})
        pnls=[t.pnl for t in portfolio.closed]; return BacktestRunResult(BacktestAnalyticsEngine().calculate(req.initial_equity,equity,pnls),equity,pnls)
