from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TrailingPolicy:
    activation_r: float = 1.0
    trail_r: float = 0.5


def update_stop(side: str, entry: float, initial_stop: float, current_price: float, current_stop: float, policy: TrailingPolicy | None = None) -> float:
    policy = policy or TrailingPolicy()
    risk = abs(entry - initial_stop)
    if risk <= 0:
        raise ValueError('initial stop must differ from entry')
    if side == 'BUY':
        profit_r = (current_price - entry) / risk
        if profit_r < policy.activation_r:
            return current_stop
        candidate = current_price - risk * policy.trail_r
        return max(current_stop, candidate)
    if side == 'SELL':
        profit_r = (entry - current_price) / risk
        if profit_r < policy.activation_r:
            return current_stop
        candidate = current_price + risk * policy.trail_r
        return min(current_stop, candidate)
    raise ValueError('side must be BUY or SELL')
