from app.execution_recovery import ExecutionRecovery,BrokerPosition
from app.order_lifecycle import OrderLifecycle,OrderStatus
from app.order_reconciliation import BrokerOrder

def test_recovery_is_safe_when_orders_and_positions_match():
    book=OrderLifecycle(); book.create('o1','NIFTY','BUY',10); book.transition('o1',OrderStatus.FILLED,10,100.0)
    report=ExecutionRecovery(book).recover([BrokerOrder('o1','NIFTY','BUY',10,OrderStatus.FILLED,10,100.0)],[BrokerPosition('NIFTY','BUY',10,100.0)])
    assert report.safe_to_resume
    assert report.position_mismatches==[]

def test_recovery_blocks_resume_on_position_mismatch():
    book=OrderLifecycle(); book.create('o1','NIFTY','BUY',10); book.transition('o1',OrderStatus.FILLED,10,100.0)
    report=ExecutionRecovery(book).recover([],[BrokerPosition('NIFTY','BUY',5,100.0)])
    assert not report.safe_to_resume
    assert report.position_mismatches

def test_duplicate_broker_event_blocks_resume():
    book=OrderLifecycle(); remote=BrokerOrder('o1','NIFTY','BUY',10,OrderStatus.FILLED,10,100.0)
    report=ExecutionRecovery(book).recover([remote,remote],[])
    assert not report.safe_to_resume
