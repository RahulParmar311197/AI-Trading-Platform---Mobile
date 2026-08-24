from app.portfolio_state import normalize_portfolio


def test_normalize_portfolio_accepts_broker_data_envelope():
    state = normalize_portfolio(
        7,
        {"user": "demo"},
        {"data": [{"trading_symbol": "NIFTY", "quantity": 10, "average_price": 100, "last_price": 105, "pnl": 50}]},
        {"data": [{"symbol": "RELIANCE", "qty": 2, "average_price": 2000, "ltp": 2010, "unrealised": 20}]},
    )
    assert state.broker == "upstox"
    assert state.account_id == 7
    assert state.positions[0].symbol == "NIFTY"
    assert state.positions[0].quantity == 10
    assert state.positions[0].side == "LONG"
    assert state.holdings[0].symbol == "RELIANCE"


def test_negative_position_is_short_and_exposure_preserves_sign():
    state = normalize_portfolio(
        1,
        {},
        [{"symbol": "NIFTY", "quantity": -5, "last_price": 100, "pnl": -25}],
        [],
    )
    assert state.positions[0].side == "SHORT"
    assert state.net_exposure == -500
    assert state.unrealized_pnl == -25


def test_portfolio_pnl_and_exposure_aggregate_positions_and_holdings():
    state = normalize_portfolio(
        1,
        {},
        [{"symbol": "NIFTY", "quantity": 2, "last_price": 100, "pnl": 15}],
        [{"symbol": "ABC", "quantity": 3, "last_price": 50, "pnl": 5}],
    )
    assert state.net_exposure == 200
    assert state.unrealized_pnl == 20


def test_malformed_top_level_payload_is_normalized_to_empty_state():
    state = normalize_portfolio(1, {}, {"data": "invalid"}, {"results": None})
    assert state.positions == []
    assert state.holdings == []
    assert state.net_exposure == 0
    assert state.unrealized_pnl == 0


def test_long_position_mark_to_market_and_gross_exposure():
    state = normalize_portfolio(
        1, {},
        [{"symbol": "NIFTY", "quantity": 10, "average_price": 100, "last_price": 105}],
        [],
    )
    assert state.positions[0].calculated_unrealized_pnl == 50
    assert state.gross_exposure == 1050
    assert state.calculated_unrealized_pnl == 50


def test_short_position_mark_to_market_is_positive_when_price_falls():
    state = normalize_portfolio(
        1, {},
        [{"symbol": "NIFTY", "quantity": -5, "average_price": 100, "last_price": 90}],
        [],
    )
    assert state.positions[0].calculated_unrealized_pnl == 50
    assert state.gross_exposure == 450
    assert state.net_exposure == -450


def test_mark_to_market_includes_holdings():
    state = normalize_portfolio(
        1, {}, [],
        [{"symbol": "ABC", "quantity": 3, "average_price": 200, "ltp": 210}],
    )
    assert state.calculated_unrealized_pnl == 30
    assert state.gross_exposure == 630
