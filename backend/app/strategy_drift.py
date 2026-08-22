from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class DriftLimits:
    min_trades:int=20
    max_drawdown:float=0.10
    max_win_rate_drop:float=0.15
    max_profit_factor_drop:float=0.30
    max_expectancy_drop:float=0.30

@dataclass(frozen=True)
class DriftResult:
    drifted:bool
    severity:str
    reasons:tuple[str,...]
    score:float


def _relative_drop(baseline:float,current:float)->float:
    if baseline<=0: return 0.0 if current>=baseline else 1.0
    return max(0.0,(baseline-current)/baseline)


def detect_strategy_drift(baseline:dict,current:dict,limits:DriftLimits|None=None)->DriftResult:
    limits=limits or DriftLimits(); reasons=[]
    trades=int(current.get('trade_count',0)); dd=float(current.get('max_drawdown',0));
    wr_drop=_relative_drop(float(baseline.get('win_rate',0)),float(current.get('win_rate',0)))
    pf_drop=_relative_drop(float(baseline.get('profit_factor',0)),float(current.get('profit_factor',0)))
    exp_drop=_relative_drop(float(baseline.get('expectancy',0)),float(current.get('expectancy',0)))
    if trades<limits.min_trades: reasons.append('INSUFFICIENT_LIVE_SAMPLE')
    if dd>limits.max_drawdown: reasons.append('DRAWDOWN_DRIFT')
    if wr_drop>limits.max_win_rate_drop: reasons.append('WIN_RATE_DRIFT')
    if pf_drop>limits.max_profit_factor_drop: reasons.append('PROFIT_FACTOR_DRIFT')
    if exp_drop>limits.max_expectancy_drop: reasons.append('EXPECTANCY_DRIFT')
    score=min(100.0,20*len(reasons))
    severity='CRITICAL' if any(x in reasons for x in ('DRAWDOWN_DRIFT','PROFIT_FACTOR_DRIFT','EXPECTANCY_DRIFT')) and len(reasons)>=2 else 'WARNING' if reasons else 'NORMAL'
    return DriftResult(bool(reasons),severity,tuple(reasons),score)
