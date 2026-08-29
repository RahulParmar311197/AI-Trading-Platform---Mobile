from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import math

from app.market_context import MarketContext
from app.ml_decision import MLDecisionConfig
from app.ml_inference import Prediction
from app.signal_confluence import SignalDecision

Decision = Literal['BUY', 'SELL', 'HOLD']


@dataclass(frozen=True)
class DecisionConfig:
    minimum_confidence: float = 0.60
    minimum_edge: float = 0.15
    confluence_weight: float = 0.0
    ml: MLDecisionConfig | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.minimum_confidence)) or not 0 <= self.minimum_confidence <= 1:
            raise ValueError('minimum_confidence must be between 0 and 1')
        if not math.isfinite(float(self.minimum_edge)) or not 0 <= self.minimum_edge <= 1:
            raise ValueError('minimum_edge must be between 0 and 1')
        if not math.isfinite(float(self.confluence_weight)) or not 0 <= self.confluence_weight <= 1:
            raise ValueError('confluence_weight must be between 0 and 1')


@dataclass(frozen=True)
class TradingDecision:
    symbol: str
    decision: Decision
    confidence: float
    bullish_score: float
    bearish_score: float
    entry: float | None
    stop_loss: float | None
    target: float | None
    reasons: tuple[str, ...]


class AIDecisionEngine:
    """Explainable decision layer; confluence and ML are optional evidence."""

    _REQUIRED_TRADE_INDICATORS = ('ema_20', 'ema_50', 'rsi_14', 'macd_histogram', 'atr_14')

    def __init__(self, config: DecisionConfig | None = None):
        self.config = config or DecisionConfig()

    def _decision_inputs_ready(self, context: MarketContext, values: dict[str, float | None]) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if context.data_quality != 'GOOD': reasons.append(f'data quality not trade-ready: {context.data_quality}')
        missing = [name for name in self._REQUIRED_TRADE_INDICATORS if values.get(name) is None]
        if missing: reasons.append(f'missing required indicators: {", ".join(missing)}')
        for name in self._REQUIRED_TRADE_INDICATORS:
            value = values.get(name)
            if value is not None and not math.isfinite(float(value)): reasons.append(f'non-finite indicator: {name}')
        rsi = values.get('rsi_14')
        if rsi is not None and math.isfinite(float(rsi)) and not 0 <= rsi <= 100: reasons.append('RSI outside 0..100')
        atr = values.get('atr_14')
        if atr is not None and math.isfinite(float(atr)) and atr <= 0: reasons.append('ATR must be positive for a trade')
        return not reasons, tuple(reasons)

    def decide(self, context: MarketContext, prediction: Prediction | None = None, ml_confidence: float = 0.0, confluence: SignalDecision | None = None) -> TradingDecision:
        context.validate()
        if not math.isfinite(float(ml_confidence)) or not 0 <= ml_confidence <= 1: raise ValueError('ml_confidence must be finite and between 0 and 1')
        if prediction is not None and prediction.label not in {'BUY', 'SELL', 'HOLD'}: raise ValueError('prediction label must be BUY, SELL, or HOLD')

        bullish = bearish = 0.0
        reasons: list[str] = []
        values = context.indicators.values
        close = context.candles[-1].close
        inputs_ready, input_reasons = self._decision_inputs_ready(context, values)
        if not inputs_ready: return TradingDecision(context.symbol, 'HOLD', 0.0, 0.0, 0.0, None, None, None, input_reasons)

        ema20, ema50, rsi = values['ema_20'], values['ema_50'], values['rsi_14']
        macd_hist, adx = values['macd_histogram'], values.get('adx_14')
        if ema20 > ema50: bullish += 1; reasons.append('EMA20 above EMA50')
        elif ema20 < ema50: bearish += 1; reasons.append('EMA20 below EMA50')
        if 50 < rsi < 70: bullish += .75; reasons.append('RSI bullish momentum')
        elif 30 < rsi < 50: bearish += .75; reasons.append('RSI bearish momentum')
        if macd_hist > 0: bullish += .75; reasons.append('MACD histogram positive')
        elif macd_hist < 0: bearish += .75; reasons.append('MACD histogram negative')
        if context.structure.trend == 'BULLISH': bullish += 1; reasons.append('bullish market structure')
        elif context.structure.trend == 'BEARISH': bearish += 1; reasons.append('bearish market structure')
        if context.structure.bos == 'BULLISH': bullish += 1; reasons.append('bullish BOS')
        elif context.structure.bos == 'BEARISH': bearish += 1; reasons.append('bearish BOS')
        if context.structure.choch == 'BULLISH': bullish += .75; reasons.append('bullish CHOCH')
        elif context.structure.choch == 'BEARISH': bearish += .75; reasons.append('bearish CHOCH')
        if context.smc.premium_discount == 'DISCOUNT': bullish += .5; reasons.append('price in discount')
        elif context.smc.premium_discount == 'PREMIUM': bearish += .5; reasons.append('price in premium')
        if context.smc.fair_value_gaps: reasons.append(f'{len(context.smc.fair_value_gaps)} recent FVG(s)')
        if context.ict.kill_zone: reasons.append(f'ICT {context.ict.kill_zone}')
        if adx is not None and math.isfinite(float(adx)) and adx >= 25: reasons.append('ADX confirms directional regime')

        if confluence is not None and self.config.confluence_weight > 0:
            weight = self.config.confluence_weight
            if confluence.action == 'BUY': bullish += weight; reasons.append(f'confluence BUY ({confluence.score:.2f})')
            elif confluence.action == 'SELL': bearish += weight; reasons.append(f'confluence SELL ({confluence.score:.2f})')
            else: reasons.append('confluence HOLD')

        total = bullish + bearish
        edge = abs(bullish - bearish) / total if total else 0.0
        confidence = max(bullish, bearish) / total if total else 0.0
        decision: Decision = 'HOLD'; entry = stop = target = None
        atr = values['atr_14']
        if confidence >= self.config.minimum_confidence and edge >= self.config.minimum_edge:
            if bullish > bearish: decision = 'BUY'; entry = close; stop = close - 1.5 * atr; target = close + 3 * atr
            elif bearish > bullish: decision = 'SELL'; entry = close; stop = close + 1.5 * atr; target = close - 3 * atr
        else: reasons.append('confidence/edge threshold not met')

        if prediction is not None and decision != 'HOLD':
            ml_label = prediction.label
            if ml_label != decision:
                if self.config.ml is not None and self.config.ml.require_agreement:
                    reasons.append('ML disagreement: trade rejected')
                    return TradingDecision(context.symbol, 'HOLD', confidence, round(bullish, 4), round(bearish, 4), None, None, None, tuple(reasons))
                confidence = max(0.0, confidence * (1.0 - (self.config.ml.weight if self.config.ml else .25))); reasons.append(f'ML disagrees: {ml_label}')
            elif ml_confidence >= (self.config.ml.min_confidence if self.config.ml else .55):
                weight = self.config.ml.weight if self.config.ml else .25
                confidence = min(.99, confidence * (1 - weight) + ml_confidence * weight); reasons.append(f'ML agrees: {ml_label} ({ml_confidence:.2f})')
            if confidence < self.config.minimum_confidence:
                reasons.append('ML-adjusted confidence below threshold')
                return TradingDecision(context.symbol, 'HOLD', round(confidence, 4), round(bullish, 4), round(bearish, 4), None, None, None, tuple(reasons))

        return TradingDecision(context.symbol, decision, round(confidence, 4), round(bullish, 4), round(bearish, 4), entry, stop, target, tuple(reasons))
