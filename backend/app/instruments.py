from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InstrumentSpec:
    """Canonical tradability metadata required before an order can be sized/submitted."""

    symbol: str
    security_id: str
    exchange_segment: str
    lot_size: int = 1
    tick_size: float = 0.05
    multiplier: float = 1.0
    tradable: bool = True

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if not self.security_id.strip():
            raise ValueError("security_id is required")
        if not self.exchange_segment.strip():
            raise ValueError("exchange_segment is required")
        if self.lot_size <= 0:
            raise ValueError("lot_size must be positive")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if self.multiplier <= 0:
            raise ValueError("multiplier must be positive")


class InstrumentProvider(Protocol):
    def resolve(self, symbol: str) -> InstrumentSpec | None: ...


class StaticInstrumentProvider:
    """Explicit instrument registry for tests/paper trading; unknown symbols fail closed."""

    def __init__(self, instruments: list[InstrumentSpec] | None = None):
        self._instruments = {item.symbol.strip().upper(): item for item in (instruments or [])}

    def resolve(self, symbol: str) -> InstrumentSpec | None:
        return self._instruments.get(symbol.strip().upper())

    def upsert(self, spec: InstrumentSpec) -> None:
        self._instruments[spec.symbol.strip().upper()] = spec
