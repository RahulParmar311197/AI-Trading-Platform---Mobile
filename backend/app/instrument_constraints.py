from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)
class InstrumentConstraints:
    tick_size: float = 0.01
    quantity_step: float = 1.0
    min_quantity: float = 1.0
    max_quantity: float | None = None
    min_notional: float | None = None

    def validate(self) -> None:
        if self.tick_size <= 0 or self.quantity_step <= 0:
            raise ValueError("tick_size and quantity_step must be positive")
        if self.min_quantity <= 0:
            raise ValueError("min_quantity must be positive")
        if self.max_quantity is not None and self.max_quantity < self.min_quantity:
            raise ValueError("max_quantity must be >= min_quantity")
        if self.min_notional is not None and self.min_notional <= 0:
            raise ValueError("min_notional must be positive")

    def normalize_price(self, price: float) -> float:
        self.validate()
        if price <= 0:
            raise ValueError("price must be positive")
        step = Decimal(str(self.tick_size))
        return float((Decimal(str(price)) / step).quantize(Decimal("1"), rounding=ROUND_DOWN) * step)

    def normalize_quantity(self, quantity: float, price: float | None = None) -> float:
        self.validate()
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        step = Decimal(str(self.quantity_step))
        normalized = float((Decimal(str(quantity)) / step).quantize(Decimal("1"), rounding=ROUND_DOWN) * step)
        if normalized < self.min_quantity:
            raise ValueError("quantity is below instrument minimum")
        if self.max_quantity is not None and normalized > self.max_quantity:
            normalized = self.max_quantity
        if price is not None and self.min_notional is not None and normalized * price < self.min_notional:
            raise ValueError("order notional is below instrument minimum")
        return normalized
