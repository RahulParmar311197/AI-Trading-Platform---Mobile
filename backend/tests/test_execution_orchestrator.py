from app.execution_orchestrator import ExecutionOrchestrator
from app.order_intent import OrderIntent
from app.order_lifecycle import OrderLifecycle


def make_order(risk=50):
    return OrderIntent(symbol='NIFTY', side='BUY', entry=100.0, stop_loss=99.0, take_profit=102.0, quantity=10, risk_amount=risk, source='SMC', confidence=0.9)


def test_safe_signal_reaches_order_lifecycle():
    book=OrderLifecycle(); result=ExecutionOrchestrator(book).submit_signal(order=make_order(),equity=10000,daily_pnl=0,open_positions=0)
    assert result.accepted
    assert len(book.orders)==1


def test_risk_rejection_stops_execution():
    book=OrderLifecycle(); result=ExecutionOrchestrator(book).submit_signal(order=make_order(500),equity=10000,daily_pnl=0,open_positions=0)
    assert not result.accepted
    assert result.reason=='RISK_REJECTED'
    assert len(book.orders)==0
