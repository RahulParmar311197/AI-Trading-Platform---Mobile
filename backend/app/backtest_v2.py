from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from datetime import date
from app.strategy import generate_signal
from app.market_data import Candle
from app.position_sizing import size_position
from app.order_intent import OrderIntent
from app.risk_gateway import authorize
from app.risk_engine import RiskLimits
from app.execution import PaperBroker, execute_paper
from app.portfolio import PaperPortfolio
from app.mtf_confirmation import completed_htf_context, confirms
from app.session_risk import SessionPolicy, trading_allowed
from app.trailing_stop import TrailingPolicy

@dataclass(frozen=True)
class BacktestV2Trade:
    symbol:str; side:str; entry:float; exit:float; quantity:float; pnl:float; entry_bar:int; exit_bar:int; reason:str

def run_backtest_v2(candles:list[Candle], starting_equity:float=100000.0, risk_percent:float=1.0, limits:RiskLimits|None=None, mtf_timeframe:str|None=None, require_mtf_alignment:bool=False, session_policy:SessionPolicy|None=None, trailing_policy:TrailingPolicy|None=None)->dict:
    if starting_equity<=0 or not candles: raise ValueError('invalid capital or candles')
    policy=session_policy or SessionPolicy()
    by_symbol=defaultdict(list)
    for c in candles: by_symbol[c.symbol.upper()].append(c)
    for symbol in by_symbol: by_symbol[symbol]=sorted(by_symbol[symbol],key=lambda c:c.timestamp)
    events=sorted((c for series in by_symbol.values() for c in series),key=lambda c:(c.timestamp,c.symbol.upper()))
    histories=defaultdict(list); portfolio=PaperPortfolio(starting_equity); broker=PaperBroker(); trades=[]; rejected=0; mtf_rejected=0; session_rejected=0; equity_curve=[]; open_entries={}; current_day:date|None=None; day_start_equity=starting_equity; daily_realized=0.0
    for event in events:
        symbol=event.symbol.upper(); histories[symbol].append(event)
        event_date=event.timestamp.date()
        if current_day != event_date:
            current_day=event_date; day_start_equity=portfolio.equity; daily_realized=0.0
        portfolio.update_trailing({symbol:event.close}, trailing_policy)
        closed=portfolio.process_ohlc_bar({symbol:event})
        for c in closed:
            daily_realized += c.realized_pnl
            meta=open_entries.pop(c.symbol,None)
            trades.append(BacktestV2Trade(c.symbol,c.side,c.entry_price,c.exit_price,c.quantity,c.realized_pnl,meta['entry_bar'] if meta else 0,len(histories[c.symbol])-1,c.reason))
        equity_curve.append(portfolio.mark({symbol:event.close})['equity'])
        allowed, _ = trading_allowed(event.timestamp, day_start_equity, daily_realized, policy)
        if not allowed: session_rejected += 1; continue
        history=histories[symbol]
        if len(history)<21 or symbol in portfolio.positions: continue
        signal=generate_signal(history)
        if signal is None or signal.action not in ('BUY','SELL'): continue
        if mtf_timeframe and require_mtf_alignment:
            context=completed_htf_context(event.timestamp,history,mtf_timeframe)
            if not confirms(signal.action,context,True): mtf_rejected+=1; continue
        entry=event.close; sizing=size_position(portfolio.equity,risk_percent,entry,signal.stop_loss)
        order=OrderIntent(symbol,signal.action,entry,signal.stop_loss,signal.target,sizing['quantity'],sizing['risk_amount'],'backtest_v2',signal.confidence)
        risk=authorize(order=order,equity=portfolio.equity,daily_pnl=daily_realized,open_positions=len(portfolio.positions),limits=limits)
        if not risk.approved: rejected+=1; continue
        fill=execute_paper(risk=risk,broker=broker); portfolio.apply_fill(order,fill); open_entries[symbol]={'entry_bar':len(history)-1}
    final_prices={symbol:series[-1].close for symbol,series in by_symbol.items() if series}
    return {'starting_equity':starting_equity,'ending_equity':portfolio.mark(final_prices)['equity'],'realized_pnl':portfolio.realized_pnl,'open_positions':len(portfolio.positions),'risk_rejected':rejected,'mtf_rejected':mtf_rejected,'session_rejected':session_rejected,'equity_curve':equity_curve,'trade_journal':[t.__dict__ for t in trades]}
