from app.portfolio_risk_aggregation import (
    OpenOrderRiskInput,
    PositionRiskInput,
    PortfolioRiskAggregator,
)


def test_aggregates_position_and_open_order_stop_risk():
    snapshot = PortfolioRiskAggregator().calculate(
        positions=[PositionRiskInput("NIFTY", 10, 1000, 950)],
        open_orders=[OpenOrderRiskInput("BANKNIFTY", 5, 2000, 1900)],
    )
    assert snapshot.open_position_risk == 500
    assert snapshot.open_order_risk == 500
    assert snapshot.total_open_risk == 1000
    assert snapshot.risk_data_available is True


def test_missing_stop_price_fails_closed():
    snapshot = PortfolioRiskAggregator().calculate(
        positions=[PositionRiskInput("NIFTY", 10, 1000, None)],
        open_orders=[],
    )
    assert snapshot.risk_data_available is False
    assert snapshot.total_open_risk == 0
    assert snapshot.unresolved_symbols == ("NIFTY",)


def test_invalid_risk_input_fails_closed():
    snapshot = PortfolioRiskAggregator().calculate(
        positions=[PositionRiskInput("NIFTY", 10, 0, 950)],
        open_orders=[],
    )
    assert snapshot.risk_data_available is False
