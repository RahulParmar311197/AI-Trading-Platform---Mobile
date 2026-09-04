from datetime import datetime, timedelta, timezone

import pytest

from backend.app.ict_engine import (
    fair_value_gaps,
    ict_context,
    liquidity_pools,
    liquidity_sweeps,
    order_blocks,
    structure,
    swings,
)
from backend.app.market_data import Candle


BASE = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)


def candle(i: int, *, open_: float = 100.0, high: float = 101.0, low: float = 99.0, close: float = 100.0, symbol: str = "NSE_TEST", timeframe: str = "5m") -> Candle:
    return Candle(
        timestamp=BASE + timedelta(minutes=5 * i),
        symbol=symbol,
        timeframe=timeframe,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
    )


def test_ict_rejects_empty_and_non_monotonic_sequences():
    with pytest.raises(ValueError):
        structure([])

    candles = [candle(0), candle(2), candle(1)]
    with pytest.raises(ValueError):
        swings(candles)


def test_ict_rejects_mixed_identity_and_non_finite_ohlcv():
    with pytest.raises(ValueError):
        fair_value_gaps([candle(0), candle(1, symbol="OTHER")])

    with pytest.raises(ValueError):
        ict_context([candle(0, close=float("nan"))])


def test_ict_parameter_validation_fails_closed():
    candles = [candle(i) for i in range(5)]
    with pytest.raises(ValueError):
        swings(candles, lookback=0)
    with pytest.raises(ValueError):
        liquidity_pools(candles, lookback=0)
    with pytest.raises(ValueError):
        liquidity_pools(candles, tolerance_bps=-1)
    with pytest.raises(ValueError):
        liquidity_pools(candles, tolerance_bps=float("inf"))
    with pytest.raises(ValueError):
        order_blocks(candles, displacement_mult=0)
    with pytest.raises(ValueError):
        order_blocks(candles, displacement_mult=float("nan"))


def test_ict_detects_fvg_and_order_block_from_valid_candles():
    fvg_candles = [
        candle(0, open_=99, high=100, low=98, close=99),
        candle(1, open_=100, high=101, low=99, close=100),
        candle(2, open_=103, high=105, low=102, close=104),
    ]
    fvgs = fair_value_gaps(fvg_candles)
    assert len(fvgs) == 1
    assert fvgs[0].direction == "BULLISH"
    assert fvgs[0].low == 100
    assert fvgs[0].high == 102

    ob_candles = [
        candle(0),
        candle(1, open_=100, high=104, low=99, close=99.5),
        candle(2, open_=99.5, high=108, low=99, close=108),
        candle(3),
    ]
    obs = order_blocks(ob_candles, displacement_mult=1.5)
    assert len(obs) == 1
    assert obs[0].direction == "BULLISH"
    assert obs[0].low == 99
    assert obs[0].high == 104
    assert obs[0].displacement > 1.5


def test_liquidity_sweeps_reject_invalid_pool_records():
    candles = [candle(i) for i in range(4)]
    with pytest.raises(ValueError):
        liquidity_sweeps(candles, [type("Pool", (), {"kind": "UNKNOWN", "price": 100.0, "tolerance": 0.001})()])
