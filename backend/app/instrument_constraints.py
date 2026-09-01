from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
import math


@dataclass(frozen=True)
class InstrumentConstraints:
    tick_size: float = 0.01
    quantity_step: float = 1.0
    min_quantity: float = 1.0
    max_quantity: float | None = None
    min_notional: float | None = None

    def validate(self) -> None:
        for name in ("tick_size", "quantity_step", "min_quantity"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if self.max_quantity is not None:
            value = float(self.max_quantity)
            if not math.isfinite(value) or value < self.min_quantity:
                raise ValueError("max_quantity must be finite and >= min_quantity")
        if self.min_notional is not None:
            value = float(self.min_notional)
            if not math.isfinite(value) or value <= 0:
                raise ValueError("min_notional must be positive and finite")

    @staticmethod
    def _aligned(value: float, step: float, field: str) -> float:
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"{field} must be positive and finite")
        ratio = Decimal(str(number)) / Decimal(str(step))
        if ratio != ratio.to_integral_value():
            raise ValueError(f"{field} is not aligned to instrument step")
        return number

    def normalize_price(self, price: float) -> float:
        self.validate()
        return self._aligned(price, self.tick_size, "price")

    def normalize_quantity(self, quantity: float, price: float | None = None) -> float:
        self.validate()
        normalized = self._aligned(quantity, self.quantity_step, "quantity")
        if normalized < self.min_quantity:
            raise ValueError("quantity is below instrument minimum")
        if self.max_quantity is not None and normalized > self.max_quantity:
            raise ValueError("quantity exceeds instrument maximum")
        if price is not None:
            price_value = self._aligned(price, self.tick_size, "price")
            if self.min_notional is not None and normalized * price_value < self.min_notional:
                raise ValueError("order notional is below instrument minimum")
        return normalized
