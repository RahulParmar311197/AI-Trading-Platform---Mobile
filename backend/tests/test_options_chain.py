import pytest

from app.options_chain import OptionQuote, chain_summary, enrich_chain, implied_volatility


def test_iv_round_trip():
    iv = implied_volatility(100, 100, 1, 0.05, "CALL", 10.450583572)
    assert abs(iv - 0.20) < 1e-5


def test_chain_enrichment_and_summary():
    quotes = [
        OptionQuote(100, "CALL", 10, 11, 10.5, 100, 20),
        OptionQuote(100, "PUT", 5, 6, 5.5, 150, 30),
    ]
    enriched = enrich_chain(quotes, 100, 1, 0.05)
    assert all(q.implied_volatility is not None for q in enriched)
    summary = chain_summary(enriched)
    assert summary["call_open_interest"] == 100
    assert summary["put_open_interest"] == 150
    assert summary["put_call_oi_ratio"] == 1.5


def test_invalid_market_price_is_rejected():
    with pytest.raises(ValueError):
        implied_volatility(100, 100, 1, 0.05, "CALL", 0)
