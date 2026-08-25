import threading

from app.durable_execution_consumer import DurableExecutionConsumer


def test_concurrent_duplicate_consumers_are_serialized(tmp_path):
    db = str(tmp_path / "consumer.db")
    message = {"event_id": "fill-concurrent", "event_type": "FILLED"}
    consumer = DurableExecutionConsumer(db)
    barrier = threading.Barrier(2)
    received = []
    results = []
    errors = []

    def worker():
        try:
            barrier.wait()
            results.append(consumer.consume(message, received.append))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert sorted(results) == [False, True]
    assert received == [message]
    consumer.close()
