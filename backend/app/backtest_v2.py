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
from app.partial_exit import PartialExitPolicy, partial_exit_quantity
from app.execution_costs import ExecutionCostModel

@dataclass(frozen=True)
class BacktestV2Trade:
    symbol:str; side:str; entry:float; exit:float; quantity:float; pnl:float; entry_bar:int; exit_bar:int; reason:str; commission:float=0.0; slippage:float=0.0

def run_backtest_v2(candles:list[Candle], starting_equity:float=100000.0, risk_percent:float=1.0, limits:RiskLimits|None=None, mtf_timeframe:str|None=None, require_mtf_alignment:bool=False, session_policy:SessionPolicy|None=None, trailing_policy:TrailingPolicy|None=None, partial_exit_policy:PartialExitPolicy|None=None, execution_costs:ExecutionCostModel|None=None)->dict:
    if starting_equity<=0 or not candles: raise ValueError('invalid capital or candles')
    policy=session_policy or SessionPolicy(); costs=execution_costs or ExecutionCostModel(); by_symbol=defaultdict(list)
    for c in candles: by_symbol[c.symbol.upper()].append(c)
    for symbol in by_symbol: by_symbol[symbol]=sorted(by_symbol[symbol],key=lambda c:c.timestamp)
    events=sorted((c for series in by_symbol.values() for c in series),key=lambda c:(c.timestamp,c.symbol.upper()))
    histories=defaultdict(list); portfolio=PaperPortfolio(starting_equity); broker=PaperBroker(costs); trades=[]; rejected=0; mtf_rejected=0; session_rejected=0; partial_rejected=0; equity_curve=[]; open_entries={}; current_day:date|None=None; day_start_equity=starting_equity; daily_realized=0.0
    for event in events:
        symbol=event.symbol.upper(); histories[symbol].append(event); event_date=event.timestamp.date()
        if current_day != event_date: current_day=event_date; day_start_equity=portfolio.equity; daily_realized=0.0
        portfolio.update_trailing({symbol:event.close}, trailing_policy)
        position=portfolio.positions.get(symbol)
        if position and partial_exit_policy and not position.partial_taken:
            qty=partial_exit_quantity(position.quantity,position.entry_price,position.initial_stop,event.close,position.side,partial_exit_policy)
            if qty>0:
                exit_px=costs.fill_price('SELL' if position.side=='BUY' else 'BUY',event.close); commission=costs.commission(exit_px,qty)
                c=portfolio.partial_close(symbol,exit_px,qty,partial_exit_policy.move_stop_to_breakeven,commission,abs(exit_px-event.close)*qty); daily_realized+=c.realized_pnl
                trades.append(BacktestV2Trade(c.symbol,c.side,c.entry_price,c.exit_price,c.quantity,c.realized_pnl,open_entries[symbol]['entry_bar'],len(histories[symbol])-1,c.reason,c.commission,c.slippage))
        closed=portfolio.process_ohlc_bar({symbol:event})
        for c in closed:
            meta=open_entries.pop(c.symbol,None); exit_side='SELL' if c.side=='BUY' else 'BUY'; exit_px=costs.fill_price(exit_side,c.exit_price); commission=costs.commission(exit_px,c.quantity); extra_slip=abs(exit_px-c.exit_price)*c.quantity
            net_pnl=c.realized_pnl + ((exit_px-c.exit_price)*c.quantity*(1 if c.side=='BUY' else -1)) - commission
            portfolio.realized_pnl += net_pnl-c.realized_pnl; portfolio.total_commission += commission; portfolio.total_slippage += extra_slip
            daily_realized += net_pnl
            trades.append(BacktestV2Trade(c.symbol,c.side,c.entry_price,exit_px,c.quantity,net_pnl,meta['entry_bar'] if meta else 0,len(histories[c.symbol])-1,c.reason,commission,extra_slip))
        equity_curve.append(portfolio.mark({symbol:event.close})['equity'])
        allowed, _=trading_allowed(event.timestamp,day_start_equity,daily_realized,policy)
        if not allowed: session_rejected+=1; continue
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
    result=portfolio.mark(final_prices)
    return {'starting_equity':starting_equity,'ending_equity':result['equity'],'realized_pnl':portfolio.realized_pnl,'open_positions':len(portfolio.positions),'risk_rejected':rejected,'mtf_rejected':mtf_rejected,'session_rejected':session_rejected,'partial_exits':sum(1 for t in trades if t.reason=='PARTIAL_TP'),'partial_rejected':partial_rejected,'total_commission':portfolio.total_commission,'total_slippage':portfolio.total_slippage,'equity_curve':equity_curve,'trade_journal':[t.__dict__ for t in trades]}
