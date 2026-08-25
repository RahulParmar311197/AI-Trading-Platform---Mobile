import time

from app.reliable_execution_outbox import ReliableExecutionOutboxPublisher
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_failed_publish_leaves_message_claimed_until_lease_expiry(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.apply_event("fill-1", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000)
    publisher = ReliableExecutionOutboxPublisher(repo)
    calls = []

    def failing(message):
        calls.append(message["event_id"])
        raise RuntimeError("broker unavailable")

    try:
        publisher.publish_once(failing, lease_seconds=0.05)
    except RuntimeError:
        pass
    assert repo.pending_outbox() == []
    assert calls == ["fill-1"]
    time.sleep(0.07)
    assert repo.pending_outbox()[0]["event_id"] == "fill-1"
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


def test_concurrent_publishers_claim_an_event_only_once(tmp_path):
    db = str(tmp_path / "execution.db")
    repo_a = TransactionalExecutionRepository(db)
    order = repo_a.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo_a.apply_event("fill-3", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000)
    repo_b = TransactionalExecutionRepository(db)
    first = repo_a.claim_outbox(limit=1, lease_seconds=1.0)
    second = repo_b.claim_outbox(limit=1, lease_seconds=1.0)
    assert [m["event_id"] for m in first] == ["fill-3"]
    assert second == []
    repo_b.mark_published(first[0]["id"], first[0]["claim_token"])
    assert repo_a.pending_outbox() == []
    repo_b.close()
    repo_a.close()


def test_expired_claim_can_be_recovered_by_another_publisher(tmp_path):
    db = str(tmp_path / "execution.db")
    repo_a = TransactionalExecutionRepository(db)
    order = repo_a.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo_a.apply_event("fill-4", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000)
    repo_b = TransactionalExecutionRepository(db)
    claimed = repo_a.claim_outbox(limit=1, lease_seconds=0.05)
    assert len(claimed) == 1
    time.sleep(0.07)
    recovered = repo_b.claim_outbox(limit=1, lease_seconds=1.0)
    assert [m["event_id"] for m in recovered] == ["fill-4"]
    repo_b.mark_published(recovered[0]["id"], recovered[0]["claim_token"])
    assert repo_a.pending_outbox() == []
    repo_b.close()
    repo_a.close()
