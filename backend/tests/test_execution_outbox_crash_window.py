from app.durable_execution_consumer import DurableExecutionConsumer
from app.execution_outbox_recovery_worker import ExecutionOutboxRecoveryWorker
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_crash_window_replays_but_downstream_effect_runs_once(tmp_path):
    execution_db = str(tmp_path / "execution.db")
    consumer_db = str(tmp_path / "consumer.db")
    repo = TransactionalExecutionRepository(execution_db)
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.apply_event("fill-crash-window", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000)
    consumer = DurableExecutionConsumer(consumer_db)
    worker = ExecutionOutboxRecoveryWorker(repo, consumer)
    effects = []

    # Simulate downstream success followed by process death before producer acknowledgement.
    original_mark = repo.mark_published
    def crash_before_ack(_message_id):
        raise RuntimeError("simulated crash before outbox acknowledgement")
    repo.mark_published = crash_before_ack

    try:
        try:
            worker.drain_once(effects.append)
        except RuntimeError:
            pass
        assert effects == [{"event_id": "fill-crash-window", "event_type": "FILLED", "payload": {"order_id": order, "broker_account_id": 1, "broker_route": "primary", "quantity": 5, "price": 1000}}]
        assert repo.pending_outbox()[0]["event_id"] == "fill-crash-window"
    finally:
        repo.mark_published = original_mark

    # Recovery sees the same event again, but durable consumer deduplication suppresses the effect.
    assert worker.drain_once(effects.append) == 1
    assert len(effects) == 1
    assert repo.pending_outbox() == []
    consumer.close()
    repo.close()
