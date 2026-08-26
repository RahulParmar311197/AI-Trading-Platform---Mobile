from __future__ import annotations
from dataclasses import dataclass
from app.confluence import score
from app.indicators import ema, atr, volatility
from app.market_data import Candle

@dataclass(frozen=True)
class FeatureVector:
    timestamp: object
    symbol: str
    ema_distance: float
    atr_normalized: float
    volatility_normalized: float
    structure_score: float
    bullish: int
    bearish: int
    liquidity_sweep: int
    fvg_state: int
    order_block_state: int
    premium_discount: int


def build_feature_vector(candles: list[Candle]) -> FeatureVector | None:
    """Build features using candles through the prediction bar only."""
    if len(candles) < 20:
        return None
    data = sorted(candles, key=lambda c: c.timestamp)
    result = score(data)
    closes = [c.close for c in data]
    highs = [c.high for c in data]
    lows = [c.low for c in data]
    last = closes[-1]
    fast = ema(closes, min(20, len(closes)))
    a = atr(highs, lows, closes, min(14, len(closes)))
    vol = volatility(closes, min(20, len(closes)))
    ict = result.get('ict', {})
    sweeps = ict.get('liquidity_sweeps') or []
    fvg = ict.get('fvg') or []
    obs = ict.get('order_blocks') or []
    latest_sweep = sweeps[-1] if sweeps else None
    latest_fvg = fvg[-1] if fvg else None
    latest_ob = obs[-1] if obs else None
    return FeatureVector(
        timestamp=data[-1].timestamp,
        symbol=data[-1].symbol,
        ema_distance=(last - fast) / a if fast is not None and a else 0.0,
        atr_normalized=a / last if a and last else 0.0,
        volatility_normalized=vol / last if vol and last else 0.0,
        structure_score=float(result.get('score', 0)),
        bullish=int(result.get('bias') == 'BULLISH'),
        bearish=int(result.get('bias') == 'BEARISH'),
        liquidity_sweep=(1 if latest_sweep and latest_sweep.get('direction') == 'BULLISH' else -1 if latest_sweep else 0),
        fvg_state=(1 if latest_fvg and latest_fvg.get('direction') == 'BULLISH' and last >= latest_fvg.get('low', last) else -1 if latest_fvg and latest_fvg.get('direction') == 'BEARISH' and last <= latest_fvg.get('high', last) else 0),
        order_block_state=(1 if latest_ob and latest_ob.get('direction') == 'BULLISH' and latest_ob.get('low', last) <= last <= latest_ob.get('high', last) else -1 if latest_ob and latest_ob.get('direction') == 'BEARISH' and latest_ob.get('low', last) <= last <= latest_ob.get('high', last) else 0),
        premium_discount=(1 if ict.get('dealing_range', {}).get('location') == 'DISCOUNT' else -1 if ict.get('dealing_range', {}).get('location') == 'PREMIUM' else 0),
    )
