from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from typing import Any, Callable

@dataclass(frozen=True)
class OptimizationResult:
    parameters:dict[str,Any]
    objective:float
    metrics:dict[str,Any]


def grid_search(parameter_grid:dict[str,list[Any]], evaluator:Callable[[dict[str,Any]],dict[str,Any]], objective:str='net_pnl', maximize:bool=True, max_drawdown_limit:float|None=None)->list[OptimizationResult]:
    if not parameter_grid: raise ValueError('parameter_grid must not be empty')
    keys=list(parameter_grid)
    if any(not values for values in parameter_grid.values()): raise ValueError('parameter values must not be empty')
    results=[]
    for values in product(*(parameter_grid[k] for k in keys)):
        params=dict(zip(keys,values)); metrics=evaluator(params); dd=float(metrics.get('max_drawdown',0.0))
        if max_drawdown_limit is not None and dd>max_drawdown_limit: continue
        value=float(metrics.get(objective,0.0)); results.append(OptimizationResult(params,value,metrics))
    results.sort(key=lambda r:r.objective,reverse=maximize)
    return results


def best_parameters(results:list[OptimizationResult])->dict[str,Any]|None:
    return results[0].parameters if results else None
