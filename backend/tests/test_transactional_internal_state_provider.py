from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_internal_state_provider import TransactionalInternalTradingStateProvider


def test_provider_reads_persistent_positions_and_open_orders(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 10)
    repo.apply_event("submit-1", order_id, "SUBMITTED")
    repo.apply_event("fill-1", order_id, "PARTIAL_FILL", price=1000, quantity=4)

    state = TransactionalInternalTradingStateProvider(repo).get_state()
    assert state.positions == {"NIFTY": 4.0}
    assert state.open_order_ids == frozenset({order_id})
    repo.close()
