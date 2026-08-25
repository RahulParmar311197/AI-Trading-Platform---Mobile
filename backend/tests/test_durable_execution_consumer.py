import pytest

from app.durable_execution_consumer import DurableExecutionConsumer


def test_duplicate_delivery_invokes_handler_once(tmp_path):
    consumer = DurableExecutionConsumer(str(tmp_path / "consumer.db"))
    received = []
    message = {"event_id": "fill-1", "event_type": "FILLED", "payload": {"quantity": 5}}
    assert consumer.consume(message, received.append) is True
    assert consumer.consume(message, received.append) is False
    assert len(received) == 1
    consumer.close()


def test_failed_handler_is_not_marked_consumed(tmp_path):
    consumer = DurableExecutionConsumer(str(tmp_path / "consumer.db"))
    message = {"event_id": "fill-retry", "event_type": "FILLED"}

    def fail(_):
        raise RuntimeError("downstream unavailable")

    with pytest.raises(RuntimeError):
        consumer.consume(message, fail)
    received = []
    assert consumer.consume(message, received.append) is True
    assert len(received) == 1
    consumer.close()
