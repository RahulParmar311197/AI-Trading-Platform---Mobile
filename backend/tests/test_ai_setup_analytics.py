from app.ai_setup_analytics import AISetupAnalytics


def test_groups_setup_dimensions():
    trades = [
        {"strategy":"SMC","direction":"bullish","timeframe":"5m","session":"LONDON","setup":"FVG","pnl":100},
        {"strategy":"SMC","direction":"bullish","timeframe":"5m","session":"LONDON","setup":"FVG","pnl":-40},
        {"strategy":"ICT","direction":"bearish","timeframe":"15m","session":"NY","setup":"MSS","pnl":60},
    ]
    result = AISetupAnalytics().analyze(trades)
    assert len(result["setups"]) == 2
    first = result["setups"][0]
    assert first["trades"] >= 1
    assert "expectancy" in first


def test_empty_setups_safe():
    result = AISetupAnalytics().analyze([])
    assert result["setups"] == []
