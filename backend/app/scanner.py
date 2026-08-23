from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.ensemble import decide
from app.market_data import Candle


@dataclass(frozen=True)
class ScanSignal:
    symbol: str
    timeframe: str
    timestamp: datetime
    action: str
    score: float
    confidence: float
    ai_probability_up: float
    technical_score: float
    regime: str
    reasons: list[str]


class MarketScanner:
    """Signal discovery only; it never submits orders or calls a broker."""

    def scan(self, candles: list[Candle], min_confidence: float = 0.35) -> ScanSignal:
        if len(candles) < 30:
            raise ValueError("at least 30 candles required")
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be between 0 and 1")
        ordered = sorted(candles, key=lambda c: c.timestamp)
        decision = decide(ordered)
        latest = ordered[-1]
        action = decision.action if decision.confidence >= min_confidence else "NO_TRADE"
        reasons = list(decision.reasons)
        if action == "NO_TRADE" and decision.action != "NO_TRADE":
            reasons.append(f"confidence below threshold: {min_confidence:.2f}")
        return ScanSignal(latest.symbol.upper(), latest.timeframe, latest.timestamp, action, decision.score, decision.confidence, decision.ai_probability_up, decision.technical_score, decision.regime, reasons)

    def scan_many(self, datasets: dict[str, list[Candle]], min_confidence: float = 0.35) -> list[ScanSignal]:
        signals = [self.scan(candles, min_confidence) for candles in datasets.values() if candles]
        return sorted(signals, key=lambda signal: signal.confidence, reverse=True)
