from __future__ import annotations
from dataclasses import dataclass
from statistics import mean,pstdev
from app.strategy import generate_signal
from app.market_data import Candle
@dataclass
class BacktestTrade:
    side:str; entry:float; exit:float; pnl:float; bars:int; reason:str

def run_backtest(candles:list[Candle],starting_equity:float=100000.0,risk_percent:float=1.0,fee_bps:float=3.0,slippage_bps:float=1.0)->dict:
    if starting_equity<=0 or risk_percent<=0 or risk_percent>5 or len(candles)<25: raise ValueError('invalid capital/risk or insufficient candles')
    if fee_bps<0 or slippage_bps<0: raise ValueError('cost parameters cannot be negative')
    equity=starting_equity; peak=equity; max_dd=0.0; trades=[]; returns=[]; equity_curve=[equity]; i=20
    while i<len(candles)-1:
        signal=generate_signal(candles[:i+1])
        if signal is None: i+=1; continue
        entry_bar=i+1; direction=1 if signal.action=='BUY' else -1; raw_entry=candles[entry_bar].open; entry=raw_entry*(1+direction*slippage_bps/10000)
        risk_amount=equity*risk_percent/100; per_unit_risk=abs(signal.entry-signal.stop_loss); quantity=risk_amount/per_unit_risk if per_unit_risk else 0
        if quantity<=0: i+=1; continue
        exit_price=candles[-1].close; reason='end_of_test'; bars=0; exit_i=len(candles)-1
        for j in range(entry_bar,len(candles)):
            bars=j-entry_bar+1; bar=candles[j]
            stop_hit=bar.low<=signal.stop_loss if direction==1 else bar.high>=signal.stop_loss
            target_hit=bar.high>=signal.target if direction==1 else bar.low<=signal.target
            if stop_hit or target_hit:
                if stop_hit: exit_price=signal.stop_loss; reason='stop_loss'
                else: exit_price=signal.target; reason='target'
                exit_i=j; break
            exit_price=bar.close; exit_i=j
        exit=exit_price*(1-direction*slippage_bps/10000); gross=(exit-entry)*quantity*direction; costs=(entry*quantity+exit*quantity)*fee_bps/10000; pnl=gross-costs; equity+=pnl; returns.append(pnl/max(equity-pnl,1e-9)); equity_curve.append(equity); peak=max(peak,equity); max_dd=max(max_dd,(peak-equity)/peak if peak else 0); trades.append(BacktestTrade(signal.action,entry,exit,pnl,bars,reason)); i=max(i+1,exit_i+1)
    wins=[t for t in trades if t.pnl>0]; losses=[t for t in trades if t.pnl<0]; gross_profit=sum(t.pnl for t in wins); gross_loss=abs(sum(t.pnl for t in losses)); avg=mean(returns) if returns else 0; sd=pstdev(returns) if len(returns)>1 else 0
    return {'starting_equity':starting_equity,'ending_equity':equity,'net_pnl':equity-starting_equity,'return_percent':(equity/starting_equity-1)*100,'trades':len(trades),'wins':len(wins),'losses':len(losses),'win_rate':len(wins)/len(trades) if trades else 0,'profit_factor':gross_profit/gross_loss if gross_loss else None,'max_drawdown_percent':max_dd*100,'sharpe':(avg/sd)*(len(returns)**.5) if sd else 0,'equity_curve':equity_curve,'trade_journal':[t.__dict__ for t in trades]}
