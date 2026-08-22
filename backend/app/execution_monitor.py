from __future__ import annotations
from dataclasses import dataclass
from app.performance_monitor import LivePerformanceMonitor, PerformanceSnapshot
from app.trading_safety_controller import SafetyDecision, evaluate_safety
from app.paper_trading_guard import GuardLimits
from app.strategy_promotion import PromotionStatus

@dataclass(frozen=True)
class MonitoredFill:
    pnl:float
    equity_after:float

class ExecutionMonitor:
    def __init__(self, promotion:PromotionStatus, baseline_metrics:dict, window_size:int=100, guard_limits:GuardLimits|None=None):
        self.promotion=promotion; self.monitor=LivePerformanceMonitor(baseline_metrics,window_size); self.guard_limits=guard_limits
        self._day_start:float|None=None; self._peak:float|None=None; self._consecutive_losses=0

    def record_fill(self, pnl:float, equity_after:float)->None:
        if self._day_start is None: self._day_start=equity_after-float(pnl)
        self._peak=max(self._peak if self._peak is not None else equity_after,equity_after)
        self._consecutive_losses=self._consecutive_losses+1 if pnl<0 else 0
        self.monitor.record_trade(pnl,equity_after)

    def evaluate(self)->tuple[PerformanceSnapshot,SafetyDecision]:
        snapshot=self.monitor.snapshot(); equity=self.monitor._equity[-1] if self.monitor._equity else (self._day_start or 0.0)
        peak=self._peak or equity; day_start=self._day_start or equity
        decision=evaluate_safety(self.promotion,equity,day_start,peak,self._consecutive_losses,snapshot.drift,self.guard_limits)
        return snapshot,decision
