from __future__ import annotations
from dataclasses import dataclass
from app.strategy import generate_signal
from app.market_data import Candle
from app.position_sizing import size_position
from app.order_intent import OrderIntent
from app.risk_gateway import authorize
from app.risk_engine import RiskLimits
from app.execution import PaperBroker, execute_paper
from app.portfolio import PaperPortfolio

@dataclass(frozen=True)
class BacktestV2Trade:
    symbol:str; side:str; entry:float; exit:float; quantity:float; pnl:float; entry_bar:int; exit_bar:int; reason:str

def run_backtest_v2(candles:list[Candle], starting_equity:float=100000.0, risk_percent:float=1.0, limits:RiskLimits|None=None)->dict:
    if starting_equity<=0 or not candles: raise ValueError('invalid capital or candles')
    candles=sorted(candles,key=lambda c:c.timestamp)
    portfolio=PaperPortfolio(starting_equity); broker=PaperBroker(); trades=[]; rejected=0; equity_curve=[]; open_entries={}
    for i in range(20,len(candles)):
        bar=candles[i]
        closed=portfolio.process_bar({bar.symbol:bar.close})
        for c in closed:
            meta=open_entries.pop(c.symbol,None)
            trades.append(BacktestV2Trade(c.symbol,c.side,c.entry_price,c.exit_price,c.quantity,c.realized_pnl,meta['entry_bar'] if meta else i,i,c.reason))
        equity_curve.append(portfolio.mark({bar.symbol:bar.close})['equity'])
        signal=generate_signal(candles[:i+1])
        if signal is None or signal.action not in ('BUY','SELL') or bar.symbol in portfolio.positions: continue
        entry=bar.close; sizing=size_position(portfolio.equity,risk_percent,entry,signal.stop_loss)
        order=OrderIntent(bar.symbol,signal.action,entry,signal.stop_loss,signal.target,sizing['quantity'],sizing['risk_amount'],'backtest_v2',signal.confidence)
        risk=authorize(order=order,equity=portfolio.equity,daily_pnl=portfolio.realized_pnl,open_positions=len(portfolio.positions),limits=limits)
        if not risk.approved: rejected+=1; continue
        fill=execute_paper(risk=risk,broker=broker); portfolio.apply_fill(order,fill); open_entries[bar.symbol]={'entry_bar':i}
    return {'starting_equity':starting_equity,'ending_equity':portfolio.mark({candles[-1].symbol:candles[-1].close})['equity'],'realized_pnl':portfolio.realized_pnl,'open_positions':len(portfolio.positions),'risk_rejected':rejected,'equity_curve':equity_curve,'trade_journal':[t.__dict__ for t in trades]}
