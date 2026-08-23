import pytest

from app.options_chain import OptionQuote
from app.options_signal import generate_signal


def quotes(call_oi=100, put_oi=100, call_volume=100, put_volume=100):
    return [
        OptionQuote(100, "CALL", 10, 11, 10.5, call_oi, call_volume),
        OptionQuote(100, "PUT", 5, 6, 5.5, put_oi, put_volume),
    ]


def test_bullish_underlying_can_generate_call_signal():
    result = generate_signal(quotes(100, 160, 100, 160), "BULLISH")
    assert result.action == "BUY_CALL"
    assert result.score > 0


def test_bearish_underlying_can_generate_put_signal():
    result = generate_signal(quotes(160, 100, 160, 100), "BEARISH")
    assert result.action == "BUY_PUT"
    assert result.score < 0


def test_balanced_neutral_chain_is_no_trade():
    result = generate_signal(quotes(), "NEUTRAL")
    assert result.action == "NO_TRADE"


def test_invalid_bias_is_rejected():
    with pytest.raises(ValueError):
        generate_signal(quotes(), "INVALID")
