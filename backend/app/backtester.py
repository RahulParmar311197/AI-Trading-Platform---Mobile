from __future__ import annotations
from dataclasses import dataclass
from app.ai_decision import AIDecisionEngine
from app.paper_portfolio import PaperPortfolio
from app.risk_position_sizing import RiskPositionSizer
from app.trade_plan import TradeAction,TradePlanValidator
from app.market_data import Candle

@dataclass(frozen=True)
class BacktestMetrics:
    initial_equity:float; final_equity:float; total_return_pct:float; trades:int; wins:int; losses:int; win_rate_pct:float; max_drawdown_pct:float; profit_factor:float

class Backtester:
    def __init__(self,initial_equity:float=1_000_000.0,risk_pct:float=1.0,min_rr:float=1.5):
        self.initial_equity=initial_equity; self.sizer=RiskPositionSizer(risk_pct); self.planner=TradePlanValidator(min_rr)
    def run(self,candles:list[Candle])->BacktestMetrics:
        if len(candles)<30:return BacktestMetrics(self.initial_equity,self.initial_equity,0,0,0,0,0,0,0)
        portfolio=PaperPortfolio(self.initial_equity); peak=self.initial_equity; max_dd=0.0
        for i in range(30,len(candles)):
            window=candles[:i+1]; decision=AIDecisionEngine().decide(window); price=candles[i].close; symbol=candles[i].symbol
            if decision.action in ('BUY','SELL') and not portfolio.open_ids:
                atr=max(0.01,(max(c.high for c in window[-14:])-min(c.low for c in window[-14:]))/14)
                stop=price-atr*1.5 if decision.action=='BUY' else price+atr*1.5; target=price+atr*1.5*self.planner.min_rr if decision.action=='BUY' else price-atr*1.5*self.planner.min_rr
                sized=self.sizer.size(portfolio.equity({symbol:price}),price,stop)
                if sized.valid: portfolio.open(self.planner.build(symbol,TradeAction(decision.action),price,stop,target,sized.quantity,sized.risk_amount))
            portfolio.update({symbol:price}); eq=portfolio.equity({symbol:price}); peak=max(peak,eq); max_dd=max(max_dd,(peak-eq)/peak*100)
        final=portfolio.equity({candles[-1].symbol:candles[-1].close}); wins=sum(t.pnl>0 for t in portfolio.closed); losses=sum(t.pnl<0 for t in portfolio.closed); gw=sum(t.pnl for t in portfolio.closed if t.pnl>0); gl=-sum(t.pnl for t in portfolio.closed if t.pnl<0); pf=gw/gl if gl else (float('inf') if gw else 0)
        return BacktestMetrics(self.initial_equity,final,(final/self.initial_equity-1)*100,len(portfolio.closed),wins,losses,wins/len(portfolio.closed)*100 if portfolio.closed else 0,max_dd,pf)
