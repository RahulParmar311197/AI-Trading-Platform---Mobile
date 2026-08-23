from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

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

    def validate(self) -> None:
        if not self.symbol or self.entry <= 0 or self.stop_loss <= 0 or self.take_profit <= 0:
            raise ValueError('invalid order prices or symbol')
        if self.quantity <= 0 or self.risk_amount <= 0:
            raise ValueError('quantity and risk_amount must be positive')
        if self.side == 'BUY' and not (self.stop_loss < self.entry < self.take_profit):
            raise ValueError('BUY requires stop < entry < target')
        if self.side == 'SELL' and not (self.take_profit < self.entry < self.stop_loss):
            raise ValueError('SELL requires target < entry < stop')
