from app.execution_alert_dispatcher import ExecutionAlertDispatcher
from app.execution_alert_events import ExecutionAlertEventStore
from app.execution_alert_worker import ExecutionAlertOutboxWorker


def test_worker_retries_failed_event_with_backoff(tmp_path):
    store = ExecutionAlertEventStore(str(tmp_path / "events.db"))
    event = store.emit_once(type("Alert", (), {"alert_id": 11})(), "CREATED")
    attempts = []

    def publish(item):
        attempts.append(item.event_id)
        if len(attempts) < 3:
            raise RuntimeError("push unavailable")

    dispatcher = ExecutionAlertDispatcher(store, publish=publish)
    worker = ExecutionAlertOutboxWorker(dispatcher, max_attempts=5, base_delay_seconds=0)
    first = worker.run_once()
    second = worker.run_once()
    third = worker.run_once()

    assert first[0].delivered is False
    assert second[0].delivered is False
    assert third[0].delivered is True
    assert attempts == [event.event_id, event.event_id, event.event_id]
