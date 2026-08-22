from __future__ import annotations
from dataclasses import dataclass
from app.paper_trading_guard import TradingMode, GuardLimits, evaluate_trading_guard
from app.strategy_drift import DriftResult
from app.strategy_promotion import PromotionStatus

@dataclass(frozen=True)
class SafetyDecision:
    mode:TradingMode
    paused:bool
    reasons:tuple[str,...]
    drift_severity:str


def evaluate_safety(promotion:PromotionStatus, equity:float, starting_day_equity:float, peak_equity:float, consecutive_losses:int, drift:DriftResult, limits:GuardLimits|None=None)->SafetyDecision:
    guard=evaluate_trading_guard(promotion,equity,starting_day_equity,peak_equity,consecutive_losses,limits)
    reasons=list(guard.reasons)
    if drift.severity=='CRITICAL':
        reasons.extend(drift.reasons or ('CRITICAL_STRATEGY_DRIFT',))
        return SafetyDecision(TradingMode.DISABLED,True,tuple(dict.fromkeys(reasons)),'CRITICAL')
    if drift.severity=='WARNING':
        reasons.append('STRATEGY_DRIFT_WARNING')
        if guard.mode==TradingMode.LIVE:
            return SafetyDecision(TradingMode.PAPER,False,tuple(dict.fromkeys(reasons)),'WARNING')
    return SafetyDecision(guard.mode,guard.paused,tuple(dict.fromkeys(reasons)) ,drift.severity)
