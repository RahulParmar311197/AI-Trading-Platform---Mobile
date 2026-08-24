from datetime import datetime, timezone

import pytest

from app.risk_gate import PreTradeRiskGate


def test_trading_day_key_uses_configured_timezone():
    instant = datetime(2026, 8, 23, 19, 0, tzinfo=timezone.utc)
    assert PreTradeRiskGate.trading_day_key(instant, "Asia/Kolkata") == "2026-08-24"
    assert PreTradeRiskGate.trading_day_key(instant, "UTC") == "2026-08-23"


def test_invalid_trading_timezone_fails_closed():
    with pytest.raises(ValueError, match="invalid trading-day timezone"):
        PreTradeRiskGate.trading_day_key(timezone_name="Not/AZone")
