from __future__ import annotations
from dataclasses import dataclass, replace
import math
from typing import Literal

from app.instrument_constraints import InstrumentConstraints

Side = Literal['BUY','SELL']

@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: Side
    entry: float
    stop_loss: float
    take_profit: float
    quantity: float
    risk_amount: float
    source: str
    confidence: float = 0.0
    constraints: InstrumentConstraints | None = None

    def normalized(self) -> 'OrderIntent':
        """Return a broker-safe order using the configured instrument constraints."""
        if self.constraints is None:
            return self
        normalized_entry = self.constraints.normalize_price(self.entry)
        return replace(
            self,
            entry=normalized_entry,
            stop_loss=self.constraints.normalize_price(self.stop_loss),
            take_profit=self.constraints.normalize_price(self.take_profit),
            quantity=self.constraints.normalize_quantity(self.quantity, price=normalized_entry),
        )

    def validate(self) -> None:
        values = (self.entry, self.stop_loss, self.take_profit, self.quantity, self.risk_amount, self.confidence)
        if not self.symbol or self.side not in ('BUY', 'SELL'):
            raise ValueError('invalid order symbol or side')
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError('order values must be finite')
        if self.entry <= 0 or self.stop_loss <= 0 or self.take_profit <= 0:
            raise ValueError('invalid order prices or symbol')
        if self.quantity <= 0 or self.risk_amount <= 0:
            raise ValueError('quantity and risk_amount must be positive')
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError('confidence must be between 0 and 1')
        if self.side == 'BUY' and not (self.stop_loss < self.entry < self.take_profit):
            raise ValueError('BUY requires stop < entry < target')
        if self.side == 'SELL' and not (self.take_profit < self.entry < self.stop_loss):
            raise ValueError('SELL requires target < entry < stop')
