from app import confluence


def test_choch_takes_priority_over_bos(monkeypatch):
    monkeypatch.setattr(
        confluence,
        "structure",
        lambda candles: {
            "bos": "BULLISH",
            "choch": "BEARISH",
            "liquidity_sweeps": [],
            "fvg": [],
            "order_blocks": [],
            "dealing_range": {"location": "EQUILIBRIUM"},
        },
    )
    monkeypatch.setattr(confluence, "ema", lambda *args: 100.0)
    monkeypatch.setattr(confluence, "atr", lambda *args: 1.0)
    candles = [type("C", (), {"close": 100, "high": 101, "low": 99})()]
    result = confluence.score(candles)
    assert result["score"] == -2
    assert result["reasons"] == ["bearish CHoCH"]


def test_bos_is_used_when_no_choch(monkeypatch):
    monkeypatch.setattr(
        confluence,
        "structure",
        lambda candles: {
            "bos": "BULLISH",
            "choch": None,
            "liquidity_sweeps": [],
            "fvg": [],
            "order_blocks": [],
            "dealing_range": {"location": "EQUILIBRIUM"},
        },
    )
    monkeypatch.setattr(confluence, "ema", lambda *args: 100.0)
    monkeypatch.setattr(confluence, "atr", lambda *args: 1.0)
    candles = [type("C", (), {"close": 100, "high": 101, "low": 99})()]
    result = confluence.score(candles)
    assert result["score"] == 2
    assert result["reasons"] == ["bullish BOS"]
