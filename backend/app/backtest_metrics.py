from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class BacktestMetrics:
    total_return:float; net_pnl:float; win_rate:float; profit_factor:float; expectancy:float
    max_drawdown:float; sharpe:float; average_win:float; average_loss:float; trade_count:int
    total_commission:float; total_slippage:float


def calculate_metrics(starting_equity:float, ending_equity:float, trade_journal:list[dict], equity_curve:list[float], total_commission:float=0.0, total_slippage:float=0.0)->BacktestMetrics:
    if starting_equity<=0: raise ValueError('starting_equity must be positive')
    pnls=[float(t.get('pnl',0.0)) for t in trade_journal]; wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<0]
    gross_profit=sum(wins); gross_loss=abs(sum(losses)); count=len(pnls)
    win_rate=len(wins)/count if count else 0.0; profit_factor=gross_profit/gross_loss if gross_loss else (float('inf') if gross_profit else 0.0)
    expectancy=sum(pnls)/count if count else 0.0; average_win=gross_profit/len(wins) if wins else 0.0; average_loss=sum(losses)/len(losses) if losses else 0.0
    peak=starting_equity; max_dd=0.0
    for value in equity_curve:
        peak=max(peak,value); max_dd=max(max_dd,(peak-value)/peak if peak else 0.0)
    returns=[]
    previous=starting_equity
    for value in equity_curve:
        if previous: returns.append((value-previous)/previous)
        previous=value
    if len(returns)>1:
        mean=sum(returns)/len(returns); variance=sum((r-mean)**2 for r in returns)/(len(returns)-1); stdev=sqrt(variance); sharpe=(mean/stdev)*sqrt(252) if stdev else 0.0
    else: sharpe=0.0
    return BacktestMetrics((ending_equity-starting_equity)/starting_equity,ending_equity-starting_equity,win_rate,profit_factor,expectancy,max_dd,sharpe,average_win,average_loss,count,total_commission,total_slippage)


def compare_backtests(results:list[dict])->list[dict]:
    out=[]
    for result in results:
        m=calculate_metrics(result['starting_equity'],result['ending_equity'],result.get('trade_journal',[]),result.get('equity_curve',[]),result.get('total_commission',0),result.get('total_slippage',0))
        row={'strategy':result.get('strategy','unknown'),**m.__dict__}; out.append(row)
    return out
