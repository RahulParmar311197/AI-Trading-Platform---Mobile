from app.transactional_execution_repository import TransactionalExecutionRepository


def test_event_state_and_outbox_are_atomic_and_durable(tmp_path):
    path=str(tmp_path/"execution.db")
    repo=TransactionalExecutionRepository(path)
    order=repo.create_order("NIFTY","BUY",10)
    assert repo.apply_event("s1",order,"SUBMITTED") is True
    assert repo.apply_event("f1",order,"PARTIAL_FILL",price=1000,quantity=4) is True
    assert repo.apply_event("f1",order,"PARTIAL_FILL",price=1000,quantity=4) is False
    assert repo.snapshot().positions == {"NIFTY":4.0}
    assert len(repo.pending_outbox()) == 2
    repo.close()
    reopened=TransactionalExecutionRepository(path)
    assert reopened.snapshot().positions == {"NIFTY":4.0}
    assert reopened.apply_event("f2",order,"FILLED",price=1000,quantity=6) is True
    assert reopened.snapshot().positions == {"NIFTY":10.0}
    reopened.close()
