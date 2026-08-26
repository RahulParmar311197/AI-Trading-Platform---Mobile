from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ml_features import FeatureVector


@dataclass(frozen=True)
class CanonicalMLInput:
    features: FeatureVector


def legacy_payload_to_ml_input(payload: dict[str, Any]) -> CanonicalMLInput:
    """Translate legacy AI feature payloads into the canonical ML schema.

    Missing canonical fields are rejected rather than silently fabricated.
    Legacy-only fields remain outside the canonical contract.
    """
    required = (
        'timestamp', 'symbol', 'ema_distance', 'atr_normalized',
        'volatility_normalized', 'structure_score', 'bullish', 'bearish',
        'liquidity_sweep', 'fvg_state', 'order_block_state', 'premium_discount',
    )
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f'missing canonical ML fields: {", ".join(missing)}')
    features = FeatureVector(
        timestamp=payload['timestamp'],
        symbol=str(payload['symbol']),
        ema_distance=float(payload['ema_distance']),
        atr_normalized=float(payload['atr_normalized']),
        volatility_normalized=float(payload['volatility_normalized']),
        structure_score=float(payload['structure_score']),
        bullish=int(payload['bullish']),
        bearish=int(payload['bearish']),
        liquidity_sweep=int(payload['liquidity_sweep']),
        fvg_state=int(payload['fvg_state']),
        order_block_state=int(payload['order_block_state']),
        premium_discount=int(payload['premium_discount']),
    )
    return CanonicalMLInput(features)
