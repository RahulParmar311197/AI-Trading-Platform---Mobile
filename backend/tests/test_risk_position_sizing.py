from app.risk_position_sizing import RiskPositionSizer


def test_position_size_respects_risk_and_value_limits():
    r = RiskPositionSizer(1, 20).size(100000, 100, 95)
    assert r.valid
    assert r.quantity == 200
    assert r.max_loss <= 1000


def test_zero_stop_distance_rejected():
    r = RiskPositionSizer().size(100000, 100, 100)
    assert not r.valid
    assert 'STOP_DISTANCE_ZERO' in r.reasons


def test_tiny_risk_can_block_trade():
    r = RiskPositionSizer(0.01, 1).size(1000, 100, 90)
    assert not r.valid
    assert r.quantity == 0
