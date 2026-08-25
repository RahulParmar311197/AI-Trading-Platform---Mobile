from app.sqlite_execution_event_store import SQLiteExecutionEventStore


def test_event_id_survives_store_reopen(tmp_path):
    path = str(tmp_path / "execution_events.db")
    first = SQLiteExecutionEventStore(path)
    first.record("fill-123")
    assert first.contains("fill-123")
    first.close()

    second = SQLiteExecutionEventStore(path)
    assert second.contains("fill-123")
    second.record("fill-123")
    assert second.contains("fill-123")
    second.close()
