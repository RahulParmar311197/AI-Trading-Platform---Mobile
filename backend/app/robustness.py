from __future__ import annotations
from dataclasses import dataclass
from statistics import mean, pstdev

@dataclass(frozen=True)
class RobustnessResult:
    score:float
    status:str
    components:dict[str,float]
    reasons:tuple[str,...]


def calculate_robustness(windows:list[dict], min_trade_count:int=20, max_drawdown:float=0.25)->RobustnessResult:
    if not windows: return RobustnessResult(0.0,'REJECT',{},('NO_WINDOWS',))
    pnl=[float(w.get('test_metrics',{}).get('net_pnl',0)) for w in windows]
    dds=[float(w.get('test_metrics',{}).get('max_drawdown',0)) for w in windows]
    trades=[int(w.get('test_metrics',{}).get('trade_count',0)) for w in windows]
    profitable=sum(x>0 for x in pnl)/len(pnl)
    avg_pnl=mean(pnl); consistency=1.0-(pstdev(pnl)/(abs(avg_pnl)+1e-9)) if avg_pnl>0 else 0.0
    consistency=max(0.0,min(1.0,consistency)); dd_score=max(0.0,1.0-min(max(dds)/(max_drawdown or 1),1.0)); trade_score=min(1.0,mean(trades)/max(min_trade_count,1));
    score=100*(0.35*profitable+0.25*consistency+0.25*dd_score+0.15*trade_score)
    reasons=[]
    if profitable<0.5: reasons.append('LOW_OOS_WIN_RATE')
    if max(dds)>max_drawdown: reasons.append('EXCESSIVE_DRAWDOWN')
    if mean(trades)<min_trade_count: reasons.append('LOW_TRADE_COUNT')
    status='PASS' if score>=70 and not reasons else 'WARNING' if score>=50 else 'REJECT'
    return RobustnessResult(score,status,{'oos_win_rate':profitable,'consistency':consistency,'drawdown_score':dd_score,'trade_count_score':trade_score},tuple(reasons))
