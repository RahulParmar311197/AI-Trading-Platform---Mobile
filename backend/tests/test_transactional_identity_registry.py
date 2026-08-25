from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository
from app.transactional_identity_registry import TransactionalIdentityRegistry


def test_registry_facade_uses_single_repository(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="upstox")
    registry = TransactionalIdentityRegistry(repo)
    identity = OrderIdentity(order_id, "upstox", "broker-1")
    registry.bind(identity)
    assert registry.by_broker("upstox", "broker-1") == identity
    assert repo.get_identity_by_broker("upstox", "broker-1") == identity
    repo.close()
