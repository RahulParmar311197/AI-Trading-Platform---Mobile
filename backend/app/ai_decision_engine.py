from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.market_context import MarketContext
from app.ml_decision import MLDecisionConfig
from app.ml_inference import Prediction

Decision = Literal['BUY', 'SELL', 'HOLD']


@dataclass(frozen=True)
class DecisionConfig:
    minimum_confidence: float = 0.60
    minimum_edge: float = 0.15
    ml: MLDecisionConfig | None = None


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
    """Explainable decision layer; ML is optional evidence and risk/execution authorize."""

    def __init__(self, config: DecisionConfig | None = None):
        self.config = config or DecisionConfig()
        if not 0 <= self.config.minimum_confidence <= 1:
            raise ValueError('minimum_confidence must be between 0 and 1')
        if not 0 <= self.config.minimum_edge <= 1:
            raise ValueError('minimum_edge must be between 0 and 1')

    def decide(self, context: MarketContext, prediction: Prediction | None = None, ml_confidence: float = 0.0) -> TradingDecision:
        context.validate()
        bullish = 0.0
        bearish = 0.0
        reasons: list[str] = []
        values = context.indicators.values
        close = context.candles[-1].close
        ema20 = values.get('ema_20')
        ema50 = values.get('ema_50')
        rsi = values.get('rsi_14')
        macd_hist = values.get('macd_histogram')
        adx = values.get('adx_14')

        if ema20 is not None and ema50 is not None:
            if ema20 > ema50: bullish += 1; reasons.append('EMA20 above EMA50')
            elif ema20 < ema50: bearish += 1; reasons.append('EMA20 below EMA50')
        if rsi is not None:
            if 50 < rsi < 70: bullish += 0.75; reasons.append('RSI bullish momentum')
            elif 30 < rsi < 50: bearish += 0.75; reasons.append('RSI bearish momentum')
        if macd_hist is not None:
            if macd_hist > 0: bullish += 0.75; reasons.append('MACD histogram positive')
            elif macd_hist < 0: bearish += 0.75; reasons.append('MACD histogram negative')
        if context.structure.trend == 'BULLISH': bullish += 1; reasons.append('bullish market structure')
        elif context.structure.trend == 'BEARISH': bearish += 1; reasons.append('bearish market structure')
        if context.structure.bos == 'BULLISH': bullish += 1; reasons.append('bullish BOS')
        elif context.structure.bos == 'BEARISH': bearish += 1; reasons.append('bearish BOS')
        if context.structure.choch == 'BULLISH': bullish += 0.75; reasons.append('bullish CHOCH')
        elif context.structure.choch == 'BEARISH': bearish += 0.75; reasons.append('bearish CHOCH')
        if context.smc.premium_discount == 'DISCOUNT': bullish += 0.5; reasons.append('price in discount')
        elif context.smc.premium_discount == 'PREMIUM': bearish += 0.5; reasons.append('price in premium')
        if context.smc.fair_value_gaps: reasons.append(f'{len(context.smc.fair_value_gaps)} recent FVG(s)')
        if context.ict.kill_zone: reasons.append(f'ICT {context.ict.kill_zone}')
        if adx is not None and adx >= 25: reasons.append('ADX confirms directional regime')

        total = bullish + bearish
        edge = abs(bullish - bearish) / total if total else 0.0
        confidence = max(bullish, bearish) / total if total else 0.0
        decision: Decision = 'HOLD'
        entry = stop = target = None
        if context.data_quality in {'GOOD', 'UNKNOWN'} and confidence >= self.config.minimum_confidence and edge >= self.config.minimum_edge:
            if bullish > bearish:
                decision = 'BUY'; entry = close; atr = values.get('atr_14') or 0.0; stop = close - 1.5 * atr if atr else None; target = close + 3.0 * atr if atr else None
            elif bearish > bullish:
                decision = 'SELL'; entry = close; atr = values.get('atr_14') or 0.0; stop = close + 1.5 * atr if atr else None; target = close - 3.0 * atr if atr else None
        else:
            reasons.append('confidence/edge threshold not met')

        if prediction is not None and decision != 'HOLD':
            ml_label = prediction.label
            if ml_label != decision:
                if self.config.ml is not None and self.config.ml.require_agreement:
                    reasons.append('ML disagreement: trade rejected')
                    return TradingDecision('HOLD', confidence, round(bullish, 4), round(bearish, 4), None, None, None, tuple(reasons))
                confidence = max(0.0, confidence * (1.0 - (self.config.ml.weight if self.config.ml else 0.25)))
                reasons.append(f'ML disagrees: {ml_label}')
            elif ml_confidence >= (self.config.ml.min_confidence if self.config.ml else 0.55):
                weight = self.config.ml.weight if self.config.ml else 0.25
                confidence = min(0.99, confidence * (1.0 - weight) + ml_confidence * weight)
                reasons.append(f'ML agrees: {ml_label} ({ml_confidence:.2f})')
            if confidence < self.config.minimum_confidence:
                reasons.append('ML-adjusted confidence below threshold')
                return TradingDecision('HOLD', round(confidence, 4), round(bullish, 4), round(bearish, 4), None, None, None, tuple(reasons))

        return TradingDecision(decision, round(confidence, 4), round(bullish, 4), round(bearish, 4), entry, stop, target, tuple(reasons))
