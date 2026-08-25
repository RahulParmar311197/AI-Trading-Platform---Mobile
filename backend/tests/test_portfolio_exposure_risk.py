import pytest

from app.portfolio_exposure_risk import ExposureLimits, PortfolioExposureRisk


def gate(**limits):
    return PortfolioExposureRisk(ExposureLimits(**limits))


def test_allows_order_within_limits():
    result = gate(max_symbol_quantity=100, max_symbol_notional=20000, max_total_notional=50000, max_symbol_concentration=0.80).evaluate(
        "NIFTY", "BUY", 10, 1000, {"NIFTY": 20, "BANKNIFTY": 10}
    )
    assert result.approved is True


@pytest.mark.parametrize("limits, reason", [
    ({"max_symbol_quantity": 25}, "max symbol quantity"),
    ({"max_symbol_notional": 25000}, "max symbol notional"),
    ({"max_total_notional": 25000}, "max total portfolio exposure"),
    ({"max_symbol_concentration": 0.50}, "max symbol concentration"),
])
def test_blocks_exposure_breaches(limits, reason):
    result = gate(**limits).evaluate("NIFTY", "BUY", 10, 1000, {"NIFTY": 20, "BANKNIFTY": 10})
    assert result.approved is False
    assert reason in result.reason


def test_open_order_exposure_counts():
    result = gate(max_total_notional=35000).evaluate(
        "NIFTY", "BUY", 10, 1000, {"NIFTY": 10, "BANKNIFTY": 10}, open_order_notional=16000
    )
    assert result.approved is False


def test_missing_positions_fail_closed():
    result = gate(max_total_notional=100000).evaluate(
        "NIFTY", "BUY", 1, 1000, {}, positions_available=False
    )
    assert result.approved is False
    assert "unavailable" in result.reason
