import pytest

from app.transactional_execution_repository import TransactionalExecutionRepository


def test_event_state_and_outbox_are_atomic_and_durable(tmp_path):
    path = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(path)
    order = repo.create_order("NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    assert repo.apply_event("s1", order, "SUBMITTED", broker_account_id=7, broker_route="upstox:account:7") is True
    assert repo.apply_event("f1", order, "PARTIAL_FILL", broker_account_id=7, broker_route="upstox:account:7", price=1000, quantity=4) is True
    assert repo.apply_event("f1", order, "PARTIAL_FILL", broker_account_id=7, broker_route="upstox:account:7", price=1000, quantity=4) is False
    assert repo.snapshot().positions == {(7, "upstox:account:7", "NIFTY"): 4.0}
    assert len(repo.pending_outbox()) == 2
    repo.close()

    reopened = TransactionalExecutionRepository(path)
    assert reopened.snapshot().positions == {(7, "upstox:account:7", "NIFTY"): 4.0}
    assert reopened.apply_event("f2", order, "FILLED", broker_account_id=7, broker_route="upstox:account:7", price=1000, quantity=6) is True
    assert reopened.snapshot().positions == {(7, "upstox:account:7", "NIFTY"): 10.0}
    reopened.close()


def test_same_symbol_isolated_between_broker_accounts(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_a = repo.create_order("NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    order_b = repo.create_order("NIFTY", "BUY", 5, broker_account_id=8, broker_route="upstox:account:8")
    assert repo.apply_event("fill-a", order_a, "FILL", broker_account_id=7, broker_route="upstox:account:7", quantity=10, price=1000) is True
    assert repo.apply_event("fill-b", order_b, "FILL", broker_account_id=8, broker_route="upstox:account:8", quantity=5, price=1001) is True
    assert repo.snapshot().positions == {
        (7, "upstox:account:7", "NIFTY"): 10.0,
        (8, "upstox:account:8", "NIFTY"): 5.0,
    }
    repo.close()


def test_wrong_broker_account_cannot_apply_event(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    with pytest.raises(ValueError, match="broker account identity mismatch"):
        repo.apply_event("wrong-account", order, "FILL", broker_account_id=8, broker_route="upstox:account:8", quantity=1, price=1000)
    assert repo.snapshot().positions == {}
    repo.close()
