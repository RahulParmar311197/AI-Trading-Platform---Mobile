from app.portfolio_reconciliation_service import PortfolioReconciliationService


def test_matching_positions_are_safe():
    result = PortfolioReconciliationService().compare({'NIFTY': 10}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.matched is True
    assert result.mismatches == ()


def test_mismatch_is_explicit_and_fail_closed():
    result = PortfolioReconciliationService().compare({'NIFTY': 7}, [{'symbol': 'NIFTY', 'quantity': 10}])
    assert result.matched is False
    assert result.mismatches[0].symbol == 'NIFTY'
    assert result.mismatches[0].local_quantity == 7
    assert result.mismatches[0].broker_quantity == 10


def test_remote_only_position_is_detected():
    result = PortfolioReconciliationService().compare({}, [{'symbol': 'BANKNIFTY', 'quantity': -5}])
    assert result.matched is False
    assert result.mismatches[0].broker_quantity == -5


def test_short_position_is_normalized_to_signed_quantity():
    result = PortfolioReconciliationService().compare({'NIFTY': -10}, [{'symbol': 'NIFTY', 'quantity': 10, 'side': 'SELL'}])
    assert result.matched is True


def test_multiple_broker_rows_are_aggregated():
    result = PortfolioReconciliationService().compare({'NIFTY': 15}, [{'symbol': 'NIFTY', 'quantity': 10, 'side': 'BUY'}, {'symbol': 'NIFTY', 'quantity': 5, 'side': 'BUY'}])
    assert result.matched is True


def test_trading_symbol_alias_is_supported():
    result = PortfolioReconciliationService().compare({}, [{'trading_symbol': 'BANKNIFTY', 'quantity': 1, 'side': 'BUY'}])
    assert result.matched is False
    assert result.mismatches[0].symbol == 'BANKNIFTY'
