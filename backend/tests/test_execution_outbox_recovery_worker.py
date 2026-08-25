import pytest

from app.durable_execution_consumer import DurableExecutionConsumer
from app.execution_outbox_recovery_worker import ExecutionOutboxRecoveryWorker
from app.transactional_execution_repository import TransactionalExecutionRepository


def _setup(tmp_path, event_id="fill-recovery"):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.apply_event(event_id, order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000)
    consumer = DurableExecutionConsumer(str(tmp_path / "consumer.db"))
    return repo, consumer, ExecutionOutboxRecoveryWorker(repo, consumer)


def test_recovery_worker_drains_pending_message(tmp_path):
    repo, consumer, worker = _setup(tmp_path)
    received = []
    assert worker.drain_once(received.append) == 1
    assert received[0]["event_id"] == "fill-recovery"
    assert repo.pending_outbox() == []
    consumer.close(); repo.close()


def test_downstream_failure_leaves_outbox_pending(tmp_path):
    repo, consumer, worker = _setup(tmp_path, "fill-failure")

    def fail(_):
        raise RuntimeError("downstream unavailable")

    with pytest.raises(RuntimeError):
        worker.drain_once(fail)
    assert repo.pending_outbox()[0]["event_id"] == "fill-failure"
    consumer.close(); repo.close()


def test_retry_after_failure_is_deduplicated(tmp_path):
    repo, consumer, worker = _setup(tmp_path, "fill-retry")
    attempts = []

    def fail_once(message):
        attempts.append(message["event_id"])
        if len(attempts) == 1:
            raise RuntimeError("temporary failure")

    with pytest.raises(RuntimeError):
        worker.drain_once(fail_once)
    assert worker.drain_once(fail_once) == 1
    assert repo.pending_outbox() == []
    assert attempts == ["fill-retry", "fill-retry"]
    consumer.close(); repo.close()
