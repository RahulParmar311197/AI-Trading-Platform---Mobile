import pytest

from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_internal_state_provider import TransactionalInternalTradingStateProvider


def test_provider_reads_persistent_positions_and_open_orders(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    repo.apply_event("submit-1", order_id, "SUBMITTED", broker_account_id=7, broker_route="upstox:account:7")
    repo.apply_event("fill-1", order_id, "PARTIAL_FILL", broker_account_id=7, broker_route="upstox:account:7", price=1000, quantity=4)

    provider = TransactionalInternalTradingStateProvider(repo)
    state = provider.get_state_for_account(broker_account_id=7, broker_route="upstox:account:7")
    assert state.positions == {"NIFTY": 4.0}
    assert state.open_order_ids == frozenset({order_id})
    repo.close()


def test_unscoped_provider_fails_closed_for_multiple_accounts(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    account_a = repo.create_order("NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    account_b = repo.create_order("NIFTY", "BUY", 5, broker_account_id=8, broker_route="upstox:account:8")
    repo.apply_event("fill-a", account_a, "FILLED", broker_account_id=7, broker_route="upstox:account:7", price=1000, quantity=10)
    repo.apply_event("fill-b", account_b, "FILLED", broker_account_id=8, broker_route="upstox:account:8", price=1000, quantity=5)

    provider = TransactionalInternalTradingStateProvider(repo)
    with pytest.raises(RuntimeError, match="multiple broker accounts"):
        provider.get_state()

    assert provider.get_state_for_account(broker_account_id=7, broker_route="upstox:account:7").positions == {"NIFTY": 10.0}
    assert provider.get_state_for_account(broker_account_id=8, broker_route="upstox:account:8").positions == {"NIFTY": 5.0}
    repo.close()
