from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class BacktestAnalytics:
    initial_equity:float; final_equity:float; total_return_pct:float; trades:int; wins:int; losses:int; win_rate_pct:float; profit_factor:float; expectancy:float; max_drawdown_pct:float; sharpe:float; sortino:float; largest_win:float; largest_loss:float; max_consecutive_wins:int; max_consecutive_losses:int

class BacktestAnalyticsEngine:
    def calculate(self,initial_equity:float,equity_curve:list[float],trade_pnls:list[float],periods_per_year:float=252.0)->BacktestAnalytics:
        if initial_equity<=0 or periods_per_year<=0: raise ValueError('invalid analytics inputs')
        curve=equity_curve or [initial_equity]; final=curve[-1]; total=(final/initial_equity-1)*100
        wins=[x for x in trade_pnls if x>0]; losses=[x for x in trade_pnls if x<0]; trades=len(trade_pnls); wr=len(wins)/trades*100 if trades else 0; gw=sum(wins); gl=abs(sum(losses)); pf=gw/gl if gl else (float('inf') if gw else 0); exp=sum(trade_pnls)/trades if trades else 0
        peak=curve[0]; max_dd=0
        for e in curve: peak=max(peak,e); max_dd=max(max_dd,(peak-e)/peak*100 if peak else 0)
        returns=[curve[i]/curve[i-1]-1 for i in range(1,len(curve)) if curve[i-1]]; mean=sum(returns)/len(returns) if returns else 0; sd=sqrt(sum((r-mean)**2 for r in returns)/len(returns)) if returns else 0; downside=sqrt(sum(min(r,0)**2 for r in returns)/len(returns)) if returns else 0; scale=sqrt(periods_per_year)
        sharpe=mean/sd*scale if sd else 0; sortino=mean/downside*scale if downside else 0; cw=cl=maxcw=maxcl=0
        for x in trade_pnls:
            if x>0: cw+=1; cl=0
            elif x<0: cl+=1; cw=0
            else: cw=cl=0
            maxcw=max(maxcw,cw); maxcl=max(maxcl,cl)
        return BacktestAnalytics(initial_equity,final,total,trades,len(wins),len(losses),wr,pf,exp,max_dd,sharpe,sortino,max(wins) if wins else 0,min(losses) if losses else 0,maxcw,maxcl)
