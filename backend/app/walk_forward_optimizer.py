from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from app.walk_forward import build_windows
from app.parameter_optimizer import grid_search, OptimizationResult

@dataclass(frozen=True)
class WalkForwardOptimizationResult:
    windows:list[dict]
    aggregate:dict


def optimize_walk_forward(candles:list[Any], train_size:int, test_size:int, parameter_grid:dict[str,list[Any]], train_evaluator:Callable[[list[Any],dict[str,Any]],dict[str,Any]], test_evaluator:Callable[[list[Any],dict[str,Any]],dict[str,Any]], objective:str='net_pnl', max_drawdown_limit:float|None=None, step:int|None=None)->WalkForwardOptimizationResult:
    rows=[]
    for window in build_windows(len(candles),train_size,test_size,step):
        train=candles[window.train_start:window.train_end]; test=candles[window.test_start:window.test_end]
        ranked=grid_search(parameter_grid,lambda p:train_evaluator(train,p),objective=objective,max_drawdown_limit=max_drawdown_limit)
        if not ranked: continue
        best:OptimizationResult=ranked[0]
        oos=test_evaluator(test,best.parameters)
        rows.append({'train_start':window.train_start,'train_end':window.train_end,'test_start':window.test_start,'test_end':window.test_end,'parameters':best.parameters,'train_metrics':best.metrics,'test_metrics':oos})
    pnls=[float(r['test_metrics'].get('net_pnl',0.0)) for r in rows]
    positive=[p for p in pnls if p>0]
    aggregate={'windows':len(rows),'oos_net_pnl':sum(pnls),'profitable_windows':len(positive),'oos_window_win_rate':len(positive)/len(pnls) if pnls else 0.0}
    return WalkForwardOptimizationResult(rows,aggregate)
