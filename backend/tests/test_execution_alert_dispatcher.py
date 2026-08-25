from app.execution_alert_dispatcher import ExecutionAlertDispatcher
from app.execution_alert_events import ExecutionAlertEventStore


def test_failed_delivery_can_retry_without_duplicate_success(tmp_path):
    event_store = ExecutionAlertEventStore(str(tmp_path / "events.db"))
    event = event_store.emit_once(type("Alert", (), {"alert_id": 7})(), "CREATED")
    calls = []

    def publish(item):
        calls.append(item.event_id)
        if len(calls) == 1:
            raise RuntimeError("provider unavailable")

    dispatcher = ExecutionAlertDispatcher(event_store, publish=publish)
    first = dispatcher.dispatch_once(event.event_id)
    second = dispatcher.dispatch_once(event.event_id)
    third = dispatcher.dispatch_once(event.event_id)

    assert first.delivered is False
    assert second.delivered is True
    assert third.delivered is True
    assert second.attempts == 2
    assert third.attempts == 2
    assert calls == [event.event_id, event.event_id]
