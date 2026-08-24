from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class IndicatorSnapshot:
    values: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class StructureSnapshot:
    trend: str = "UNKNOWN"
    swing_high: float | None = None
    swing_low: float | None = None
    bos: str | None = None
    choch: str | None = None
    liquidity_sweep: str | None = None


@dataclass(frozen=True)
class SMCSnapshot:
    order_blocks: list[dict[str, Any]] = field(default_factory=list)
    fair_value_gaps: list[dict[str, Any]] = field(default_factory=list)
    premium_discount: str | None = None
    equal_highs: list[float] = field(default_factory=list)
    equal_lows: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class ICTSnapshot:
    dealing_range_high: float | None = None
    dealing_range_low: float | None = None
    optimal_trade_entry: float | None = None
    session: str | None = None
    kill_zone: str | None = None
    liquidity_target: float | None = None


@dataclass(frozen=True)
class MarketContext:
    symbol: str
    timeframe: str
    as_of: datetime
    candles: tuple[Candle, ...] = ()
    indicators: IndicatorSnapshot = field(default_factory=IndicatorSnapshot)
    structure: StructureSnapshot = field(default_factory=StructureSnapshot)
    smc: SMCSnapshot = field(default_factory=SMCSnapshot)
    ict: ICTSnapshot = field(default_factory=ICTSnapshot)
    regime: str = "UNKNOWN"
    data_quality: str = "UNKNOWN"
    features: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if not self.timeframe.strip():
            raise ValueError("timeframe is required")
        if not self.candles:
            raise ValueError("at least one candle is required")
        previous = None
        for candle in self.candles:
            if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
                raise ValueError("invalid candle OHLC")
            if candle.high < candle.low or candle.volume < 0:
                raise ValueError("invalid candle range or volume")
            if previous is not None and candle.timestamp <= previous:
                raise ValueError("candles must be strictly chronological")
            previous = candle.timestamp
        if self.data_quality not in {"UNKNOWN", "GOOD", "DEGRADED", "STALE", "INVALID"}:
            raise ValueError("invalid data_quality")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
