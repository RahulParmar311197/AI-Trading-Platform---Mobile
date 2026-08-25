from app.reliable_execution_outbox import ReliableExecutionOutboxPublisher
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_failed_publish_leaves_message_pending_for_retry(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.apply_event("fill-1", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000)
    publisher = ReliableExecutionOutboxPublisher(repo)
    calls = []

    def failing(message):
        calls.append(message["event_id"])
        raise RuntimeError("broker unavailable")

    try:
        publisher.publish_once(failing)
    except RuntimeError:
        pass
    assert repo.pending_outbox()[0]["event_id"] == "fill-1"
    assert calls == ["fill-1"]
    repo.close()


def test_successful_retry_marks_message_published(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.apply_event("fill-2", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000)
    publisher = ReliableExecutionOutboxPublisher(repo)
    received = []
    assert publisher.publish_once(lambda message: received.append(message["event_id"])) == 1
    assert received == ["fill-2"]
    assert publisher.publish_once(lambda message: received.append(message["event_id"])) == 0
    repo.close()
