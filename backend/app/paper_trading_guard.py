from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.strategy_promotion import PromotionStatus

class TradingMode(str, Enum):
    DISABLED='DISABLED'
    PAPER='PAPER'
    LIVE='LIVE'

@dataclass(frozen=True)
class GuardLimits:
    max_daily_loss:float=0.02
    max_drawdown:float=0.10
    max_consecutive_losses:int=5
    min_equity:float=0.0

@dataclass(frozen=True)
class GuardState:
    mode:TradingMode
    paused:bool
    reasons:tuple[str,...]


def evaluate_trading_guard(promotion:PromotionStatus, equity:float, starting_day_equity:float, peak_equity:float, consecutive_losses:int, limits:GuardLimits|None=None)->GuardState:
    limits=limits or GuardLimits(); reasons=[]
    if equity<=limits.min_equity: reasons.append('MIN_EQUITY_BREACH')
    daily_loss=(starting_day_equity-equity)/starting_day_equity if starting_day_equity>0 else 0.0
    drawdown=(peak_equity-equity)/peak_equity if peak_equity>0 else 0.0
    if daily_loss>limits.max_daily_loss: reasons.append('DAILY_LOSS_LIMIT')
    if drawdown>limits.max_drawdown: reasons.append('MAX_DRAWDOWN_LIMIT')
    if consecutive_losses>=limits.max_consecutive_losses: reasons.append('CONSECUTIVE_LOSS_LIMIT')
    if reasons: return GuardState(TradingMode.DISABLED,True,tuple(reasons))
    if promotion==PromotionStatus.LIVE_ELIGIBLE: return GuardState(TradingMode.LIVE,False,())
    if promotion==PromotionStatus.PAPER_ONLY: return GuardState(TradingMode.PAPER,False,('PAPER_ONLY_PROMOTION',))
    return GuardState(TradingMode.DISABLED,True,('STRATEGY_NOT_PROMOTED',))
