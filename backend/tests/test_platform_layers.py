from app.auth.security import hash_password, verify_password, create_access_token, decode_access_token
from app.ict.engine import analyze_ict
from app.risk.portfolio import PositionRisk, evaluate_portfolio


def test_auth_round_trip():
    digest = hash_password("strong-password")
    assert verify_password("strong-password", digest)
    assert not verify_password("wrong-password", digest)
    assert decode_access_token(create_access_token("alice"))["sub"] == "alice"


def test_ict_signal():
    candles = [{"high": 10+i, "low": 8+i, "close": 9+i} for i in range(6)]
    result = analyze_ict("TEST", candles)
    assert result.bias == "bullish"
    assert result.score > 0


def test_portfolio_veto():
    result = evaluate_portfolio([PositionRisk("A", 400, 0), PositionRisk("B", 400, 0)], 1000)
    assert result.allowed is False
    assert result.reasons
