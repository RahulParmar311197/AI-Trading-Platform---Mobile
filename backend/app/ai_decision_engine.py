from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.market_context import MarketContext

Decision = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class DecisionConfig:
    minimum_confidence: float = 0.60
    minimum_edge: float = 0.15


@dataclass(frozen=True)
class TradingDecision:
    decision: Decision
    confidence: float
    bullish_score: float
    bearish_score: float
    entry: float | None
    stop_loss: float | None
    target: float | None
    reasons: tuple[str, ...]


class AIDecisionEngine:
    """Explainable deterministic decision layer. It proposes; risk/execution authorize."""

    def __init__(self, config: DecisionConfig | None = None):
        self.config = config or DecisionConfig()
        if not 0 <= self.config.minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")

    def decide(self, context: MarketContext) -> TradingDecision:
        context.validate()
        bullish = 0.0
        bearish = 0.0
        reasons: list[str] = []
        values = context.indicators.values
        close = context.candles[-1].close
        ema20 = values.get("ema_20")
        ema50 = values.get("ema_50")
        rsi = values.get("rsi_14")
        macd_hist = values.get("macd_histogram")
        adx = values.get("adx_14")

        if ema20 is not None and ema50 is not None:
            if ema20 > ema50: bullish += 1; reasons.append("EMA20 above EMA50")
            elif ema20 < ema50: bearish += 1; reasons.append("EMA20 below EMA50")
        if rsi is not None:
            if 50 < rsi < 70: bullish += 0.75; reasons.append("RSI bullish momentum")
            elif 30 < rsi < 50: bearish += 0.75; reasons.append("RSI bearish momentum")
        if macd_hist is not None:
            if macd_hist > 0: bullish += 0.75; reasons.append("MACD histogram positive")
            elif macd_hist < 0: bearish += 0.75; reasons.append("MACD histogram negative")
        if context.structure.trend == "BULLISH": bullish += 1; reasons.append("bullish market structure")
        elif context.structure.trend == "BEARISH": bearish += 1; reasons.append("bearish market structure")
        if context.structure.bos == "BULLISH": bullish += 1; reasons.append("bullish BOS")
        elif context.structure.bos == "BEARISH": bearish += 1; reasons.append("bearish BOS")
        if context.structure.choch == "BULLISH": bullish += 0.75; reasons.append("bullish CHOCH")
        elif context.structure.choch == "BEARISH": bearish += 0.75; reasons.append("bearish CHOCH")
        if context.smc.premium_discount == "DISCOUNT": bullish += 0.5; reasons.append("price in discount")
        elif context.smc.premium_discount == "PREMIUM": bearish += 0.5; reasons.append("price in premium")
        if context.smc.fair_value_gaps:
            reasons.append(f"{len(context.smc.fair_value_gaps)} recent FVG(s)")
        if context.ict.kill_zone: reasons.append(f"ICT {context.ict.kill_zone}")
        if adx is not None and adx >= 25: reasons.append("ADX confirms directional regime")

        total = bullish + bearish
        edge = abs(bullish - bearish) / total if total else 0.0
        confidence = max(bullish, bearish) / total if total else 0.0
        decision: Decision = "HOLD"
        entry = stop = target = None
        if context.data_quality in {"GOOD", "UNKNOWN"} and confidence >= self.config.minimum_confidence and edge >= self.config.minimum_edge:
            if bullish > bearish:
                decision = "BUY"; entry = close; atr = values.get("atr_14") or 0.0; stop = close - 1.5 * atr if atr else None; target = close + 3.0 * atr if atr else None
            elif bearish > bullish:
                decision = "SELL"; entry = close; atr = values.get("atr_14") or 0.0; stop = close + 1.5 * atr if atr else None; target = close - 3.0 * atr if atr else None
        else:
            reasons.append("confidence/edge threshold not met")
        return TradingDecision(decision, round(confidence, 4), round(bullish, 4), round(bearish, 4), entry, stop, target, tuple(reasons))
