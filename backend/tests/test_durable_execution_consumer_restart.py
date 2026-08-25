from app.durable_execution_consumer import DurableExecutionConsumer


def test_consumed_event_survives_consumer_restart(tmp_path):
    db = str(tmp_path / "consumer.db")
    message = {"event_id": "fill-restart", "event_type": "FILLED"}
    received = []

    first = DurableExecutionConsumer(db)
    assert first.consume(message, received.append) is True
    first.close()

    second = DurableExecutionConsumer(db)
    assert second.consume(message, received.append) is False
    assert received == [message]
    second.close()
