from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from app.backtest_metrics import calculate_metrics
from app.strategy_drift import detect_strategy_drift, DriftLimits, DriftResult

@dataclass(frozen=True)
class PerformanceSnapshot:
    metrics:dict
    drift:DriftResult

class LivePerformanceMonitor:
    def __init__(self, baseline_metrics:dict, window_size:int=100, drift_limits:DriftLimits|None=None):
        if window_size<=0: raise ValueError('window_size must be positive')
        self.baseline_metrics=dict(baseline_metrics); self.window_size=window_size; self.drift_limits=drift_limits or DriftLimits(); self._trades=deque(maxlen=window_size); self._equity=[]; self._starting_equity:float|None=None

    def record_trade(self, pnl:float, equity_after:float):
        if self._starting_equity is None: self._starting_equity=equity_after-float(pnl)
        self._trades.append({'pnl':float(pnl)}); self._equity.append(float(equity_after));
        if len(self._equity)>self.window_size: self._equity.pop(0)

    def snapshot(self)->PerformanceSnapshot:
        if self._starting_equity is None: return PerformanceSnapshot({},DriftResult(True,'WARNING',('NO_LIVE_DATA',),0))
        ending=self._equity[-1] if self._equity else self._starting_equity
        metrics=calculate_metrics(self._starting_equity,ending,list(self._trades),self._equity)
        drift=detect_strategy_drift(self.baseline_metrics,metrics.__dict__,self.drift_limits)
        return PerformanceSnapshot(metrics.__dict__,drift)
