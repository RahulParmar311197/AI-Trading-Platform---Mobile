from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionCostModel:
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    fixed_fee: float = 0.0

    def __post_init__(self):
        if self.commission_bps < 0 or self.slippage_bps < 0 or self.fixed_fee < 0:
            raise ValueError('execution costs cannot be negative')

    def fill_price(self, side: str, reference_price: float) -> float:
        if reference_price <= 0: raise ValueError('reference_price must be positive')
        slip = self.slippage_bps / 10000.0
        if side == 'BUY': return reference_price * (1.0 + slip)
        if side == 'SELL': return reference_price * (1.0 - slip)
        raise ValueError('side must be BUY or SELL')

    def commission(self, price: float, quantity: float) -> float:
        if price < 0 or quantity < 0: raise ValueError('price and quantity must be non-negative')
        return price * quantity * self.commission_bps / 10000.0 + self.fixed_fee

    def round_trip_cost(self, entry_price: float, exit_price: float, quantity: float) -> float:
        return self.commission(entry_price, quantity) + self.commission(exit_price, quantity)
