from app.execution_recovery import BrokerPosition, ExecutionRecovery
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import BrokerOrder


def test_recovery_is_safe_when_orders_and_positions_match():
    book = OrderLifecycle()
    book.create("o1", "NIFTY", "BUY", 10)
    book.transition("o1", OrderStatus.FILLED, 10, 100.0)
    report = ExecutionRecovery(book).recover(
        [BrokerOrder("o1", "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0)],
        [BrokerPosition("NIFTY", "BUY", 10, 100.0)],
    )
    assert report.safe_to_resume
    assert report.position_mismatches == []


def test_recovery_blocks_resume_on_position_mismatch():
    book = OrderLifecycle()
    book.create("o1", "NIFTY", "BUY", 10)
    book.transition("o1", OrderStatus.FILLED, 10, 100.0)
    report = ExecutionRecovery(book).recover([], [BrokerPosition("NIFTY", "BUY", 5, 100.0)])
    assert not report.safe_to_resume
    assert report.position_mismatches


def test_broker_only_position_blocks_resume():
    book = OrderLifecycle()
    report = ExecutionRecovery(book).recover([], [BrokerPosition("BANKNIFTY", "SELL", 2, 500.0)])
    assert not report.safe_to_resume
    assert "BANKNIFTY:BROKER_ONLY_POSITION" in report.position_mismatches


def test_missing_broker_position_blocks_resume():
    book = OrderLifecycle()
    book.create("o1", "NIFTY", "SELL", 3)
    book.transition("o1", OrderStatus.FILLED, 3, 100.0)
    report = ExecutionRecovery(book).recover([], [])
    assert not report.safe_to_resume
    assert "NIFTY:POSITION_MISSING_ON_BROKER" in report.position_mismatches


def test_short_position_matches_signed_broker_quantity():
    book = OrderLifecycle()
    book.create("o1", "NIFTY", "SELL", 3)
    book.transition("o1", OrderStatus.FILLED, 3, 100.0)
    report = ExecutionRecovery(book).recover([], [BrokerPosition("NIFTY", "SELL", 3, 100.0)])
    assert report.safe_to_resume


def test_duplicate_broker_position_is_rejected():
    book = OrderLifecycle()
    try:
        ExecutionRecovery(book).recover(
            [],
            [
                BrokerPosition("NIFTY", "BUY", 1, 100.0),
                BrokerPosition("NIFTY", "BUY", 1, 100.0),
            ],
        )
    except ValueError as exc:
        assert "duplicate broker position" in str(exc)
    else:
        raise AssertionError("duplicate broker position must fail closed")


def test_duplicate_broker_event_blocks_resume():
    book = OrderLifecycle()
    remote = BrokerOrder("o1", "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0)
    report = ExecutionRecovery(book).recover([remote, remote], [])
    assert not report.safe_to_resume
