import threading

import pytest

from app.transactional_execution_repository import TransactionalExecutionRepository


def test_duplicate_event_id_applies_once(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    assert repo.apply_event("fill-1", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000) is True
    assert repo.apply_event("fill-1", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000) is False
    assert repo.snapshot().positions == {(1, "primary", "NIFTY"): 5.0}
    assert len(repo.pending_outbox()) == 1
    repo.close()


def test_concurrent_duplicate_event_id_mutates_once(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    results = []
    errors = []
    barrier = threading.Barrier(2)

    def worker():
        try:
            barrier.wait()
            results.append(repo.apply_event("fill-race", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1000))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert not errors
    assert sorted(results) == [False, True]
    assert repo.snapshot().positions == {(1, "primary", "NIFTY"): 5.0}
    assert len(repo.pending_outbox()) == 1
    repo.close()


def test_two_distinct_partial_fills_are_serialized(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="primary")
    barrier = threading.Barrier(2)
    results = []
    errors = []

    def worker(event_id):
        try:
            barrier.wait()
            results.append(repo.apply_event(event_id, order, "PARTIAL_FILL", broker_account_id=1, broker_route="primary", quantity=5, price=1000))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(event_id,)) for event_id in ("partial-a", "partial-b")]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert not errors
    assert sorted(results) == [True, True]
    assert repo.snapshot().positions == {(1, "primary", "NIFTY"): 10.0}
    assert len(repo.pending_outbox()) == 2
    repo.close()


def test_fill_overrun_is_rejected_atomically(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="primary")
    assert repo.apply_event("partial-1", order, "PARTIAL_FILL", broker_account_id=1, broker_route="primary", quantity=6, price=1000) is True
    with pytest.raises(ValueError, match="invalid fill quantity"):
        repo.apply_event("partial-2", order, "FILLED", broker_account_id=1, broker_route="primary", quantity=5, price=1001)
    assert repo.snapshot().positions == {(1, "primary", "NIFTY"): 6.0}
    assert len(repo.pending_outbox()) == 1
    repo.close()
