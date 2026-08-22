from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PartialExitPolicy:
    trigger_r: float = 1.0
    close_fraction: float = 0.5
    move_stop_to_breakeven: bool = True

    def __post_init__(self):
        if self.trigger_r <= 0 or not 0 < self.close_fraction <= 1:
            raise ValueError('invalid partial exit policy')


def partial_exit_quantity(quantity: float, entry: float, initial_stop: float, current_price: float, side: str, policy: PartialExitPolicy) -> float:
    risk = abs(entry - initial_stop)
    if risk <= 0:
        raise ValueError('initial stop must differ from entry')
    profit_r = ((current_price - entry) / risk) if side == 'BUY' else ((entry - current_price) / risk)
    if profit_r < policy.trigger_r:
        return 0.0
    return quantity * policy.close_fraction
