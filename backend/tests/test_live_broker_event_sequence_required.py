from pathlib import Path

import pytest

from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.transactional_execution_repository import TransactionalExecutionRepository


def make_repo(tmp_path: Path) -> TransactionalExecutionRepository:
    return TransactionalExecutionRepository(str(tmp_path / "execution.db"))


def test_canonical_event_preserves_valid_broker_sequence() -> None:
    event = CanonicalExecutionEvent(
        "event-1",
        "broker-1",
        "client-1",
        "NIFTY",
        "BUY",
        CanonicalExecutionEventType.PARTIAL_FILL,
        quantity=1,
        broker_account_id=1,
        broker_route="zerodha",
        event_sequence=7,
    )
    assert event.event_sequence == 7


@pytest.mark.parametrize("sequence", [-1, True, 1.5, "7"])
def test_canonical_event_rejects_invalid_broker_sequence(sequence) -> None:
    with pytest.raises(ValueError, match="event_sequence must be a non-negative integer"):
        CanonicalExecutionEvent(
            "event-1",
            "broker-1",
            "client-1",
            "NIFTY",
            "BUY",
            CanonicalExecutionEventType.SUBMITTED,
            broker_account_id=1,
            broker_route="zerodha",
            event_sequence=sequence,
        )


def test_live_broker_event_requires_ordering_token(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        with pytest.raises(TypeError):
            repo.apply_broker_event(
                "event-1",
                order_id,
                "SUBMITTED",
                broker_account_id=1,
                broker_route="zerodha",
            )
    finally:
        repo.close()


def test_live_broker_event_with_sequence_uses_durable_fence(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        assert repo.apply_broker_event(
            "event-1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=4, price=100.0, event_sequence=10
        )
        with pytest.raises(ValueError, match="stale execution event sequence"):
            repo.apply_broker_event(
                "event-2", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=1, price=100.0, event_sequence=9
            )
        assert repo.get_order(order_id)["filled_quantity"] == 4
    finally:
        repo.close()
