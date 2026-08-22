from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.robustness import RobustnessResult, calculate_robustness

class PromotionStatus(str, Enum):
    REJECT='REJECT'
    PAPER_ONLY='PAPER_ONLY'
    LIVE_ELIGIBLE='LIVE_ELIGIBLE'

@dataclass(frozen=True)
class PromotionDecision:
    status:PromotionStatus
    robustness:RobustnessResult
    reasons:tuple[str,...]


def evaluate_strategy_for_promotion(windows:list[dict], min_trade_count:int=20, max_drawdown:float=0.25, require_oos_windows:int=3)->PromotionDecision:
    if len(windows)<require_oos_windows:
        return PromotionDecision(PromotionStatus.REJECT,calculate_robustness(windows,min_trade_count,max_drawdown),('INSUFFICIENT_OOS_WINDOWS',))
    robustness=calculate_robustness(windows,min_trade_count,max_drawdown)
    if robustness.status=='PASS': return PromotionDecision(PromotionStatus.LIVE_ELIGIBLE,robustness,())
    if robustness.status=='WARNING': return PromotionDecision(PromotionStatus.PAPER_ONLY,robustness,robustness.reasons)
    return PromotionDecision(PromotionStatus.REJECT,robustness,robustness.reasons)
