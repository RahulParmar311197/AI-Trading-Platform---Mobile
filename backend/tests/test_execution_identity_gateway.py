from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.execution_identity_gateway import ExecutionIdentityGateway
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_gateway_reads_and_writes_single_repository(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    gateway = ExecutionIdentityGateway(repo)
    gateway.bind("client-1", "upstox", "broker-1")
    event = CanonicalExecutionEvent("e1", "broker-1", "wrong", "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 1, 100, broker="upstox")
    identity = gateway.resolve(event)
    assert identity is not None
    assert identity.client_order_id == "client-1"
    repo.close()
