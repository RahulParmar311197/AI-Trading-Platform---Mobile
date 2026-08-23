from app.broker_adapter import BrokerOrderRequest
from app.risk_gate import PreTradeRiskGate, RiskLimits, RiskSnapshot


def request(quantity=5, side="BUY"):
    return BrokerOrderRequest(client_order_id="risk-1", symbol="NIFTY", side=side, quantity=quantity)


def gate():
    return PreTradeRiskGate(RiskLimits(max_order_quantity=10, max_position_quantity=20, max_daily_loss=1000, max_trade_loss=200))


def ready(**kwargs):
    values = {"broker_ready": True}
    values.update(kwargs)
    return RiskSnapshot(**values)


def test_allows_order_within_limits():
    assert gate().evaluate(request(), ready()).allowed


def test_kill_switch_blocks():
    result = gate().evaluate(request(), ready(kill_switch=True))
    assert not result.allowed
    assert result.reason == "RISK_KILL_SWITCH_ACTIVE"


def test_broker_not_ready_blocks():
    result = gate().evaluate(request(), RiskSnapshot())
    assert not result.allowed
    assert result.reason == "RISK_BROKER_NOT_READY"


def test_order_quantity_limit_blocks():
    result = gate().evaluate(request(11), ready())
    assert result.reason == "RISK_MAX_ORDER_QUANTITY"


def test_projected_position_limit_blocks():
    result = gate().evaluate(request(5), ready(position_quantity=16))
    assert result.reason == "RISK_MAX_POSITION_QUANTITY"


def test_buy_reduces_short_exposure():
    result = gate().evaluate(request(5, "BUY"), ready(position_quantity=-10))
    assert result.allowed


def test_sell_reduces_long_exposure():
    result = gate().evaluate(request(5, "SELL"), ready(position_quantity=10))
    assert result.allowed


def test_sell_increases_short_exposure_and_can_breach_limit():
    result = gate().evaluate(request(5, "SELL"), ready(position_quantity=-16))
    assert not result.allowed
    assert result.reason == "RISK_MAX_POSITION_QUANTITY"


def test_invalid_side_blocks():
    result = gate().evaluate(request(5, "HOLD"), ready())
    assert result.reason == "RISK_INVALID_SIDE"


def test_invalid_position_snapshot_blocks():
    result = gate().evaluate(request(), ready(position_quantity="bad"))
    assert result.reason == "RISK_INVALID_POSITION_SNAPSHOT"


def test_daily_loss_limit_blocks_at_limit():
    result = gate().evaluate(request(), ready(daily_pnl=-1000))
    assert result.reason == "RISK_DAILY_LOSS_LIMIT"


def test_trade_loss_limit_blocks():
    result = gate().evaluate(request(), ready(projected_trade_loss=201))
    assert result.reason == "RISK_TRADE_LOSS_LIMIT"


def test_invalid_quantity_blocks():
    result = gate().evaluate(request(0), ready())
    assert result.reason == "RISK_INVALID_QUANTITY"
