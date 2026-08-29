from app.portfolio_reconciliation_service import PortfolioReconciliationResult, PositionMismatch


def test_portfolio_result_is_explicitly_named():
    result = PortfolioReconciliationResult(matched=True, mismatches=())
    assert result.matched is True
    assert not hasattr(result, "context")
    assert not hasattr(result, "generation")
    assert not hasattr(result, "snapshot_fingerprint")
    assert not hasattr(result, "verified")


def test_portfolio_result_cannot_be_confused_with_authenticated_result():
    result = PortfolioReconciliationResult(
        matched=False,
        mismatches=(PositionMismatch("NIFTY", 1, 0),),
        errors=(),
    )
    assert type(result).__name__ == "PortfolioReconciliationResult"
    assert result.mismatches[0].symbol == "NIFTY"
