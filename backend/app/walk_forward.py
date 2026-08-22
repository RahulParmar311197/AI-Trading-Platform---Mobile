from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any

@dataclass(frozen=True)
class WalkForwardWindow:
    train_start:int
    train_end:int
    test_start:int
    test_end:int

@dataclass(frozen=True)
class WalkForwardResult:
    windows:list[dict]
    aggregate:dict


def build_windows(length:int, train_size:int, test_size:int, step:int|None=None)->list[WalkForwardWindow]:
    if length<=0 or train_size<=0 or test_size<=0: raise ValueError('length and window sizes must be positive')
    step=step or test_size
    if step<=0: raise ValueError('step must be positive')
    windows=[]; start=0
    while start+train_size+test_size<=length:
        windows.append(WalkForwardWindow(start,start+train_size,start+train_size,start+train_size+test_size)); start+=step
    return windows


def run_walk_forward(candles:list[Any], train_size:int, test_size:int, optimizer:Callable[[list[Any]],Any], evaluator:Callable[[list[Any],Any],dict], step:int|None=None)->WalkForwardResult:
    windows=build_windows(len(candles),train_size,test_size,step); rows=[]
    for w in windows:
        params=optimizer(candles[w.train_start:w.train_end]); metrics=evaluator(candles[w.test_start:w.test_end],params)
        rows.append({'train_start':w.train_start,'train_end':w.train_end,'test_start':w.test_start,'test_end':w.test_end,'parameters':params,'metrics':metrics})
    pnl=[float(r['metrics'].get('net_pnl',0.0)) for r in rows]; wins=[p for p in pnl if p>0]
    aggregate={'windows':len(rows),'net_pnl':sum(pnl),'profitable_windows':len(wins),'window_win_rate':len(wins)/len(pnl) if pnl else 0.0}
    return WalkForwardResult(rows,aggregate)
