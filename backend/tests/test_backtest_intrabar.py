from app.portfolio import PaperPortfolio
from app.order_intent import OrderIntent
from app.execution import ExecutionResult


def test_long_bar_hitting_stop_and_target_uses_stop_first():
    portfolio = PaperPortfolio(100000)
    order = OrderIntent("TEST", "BUY", 100.0, 95.0, 105.0, 1.0, 5.0, "test", 1.0)
    fill = ExecutionResult(True, 1.0, 100.0, 0.0, 0.0)
    portfolio.apply_fill(order, fill)
    closed = portfolio.process_ohlc_bar({"TEST": type("Bar", (), {"high": 106.0, "low": 94.0})()})
    assert len(closed) == 1
    assert closed[0].reason == "STOP_LOSS"
    assert closed[0].exit_price == 95.0
