from pathlib import Path

import pytest

from app.transactional_execution_repository import TransactionalExecutionRepository


def make_repo(tmp_path: Path) -> TransactionalExecutionRepository:
    return TransactionalExecutionRepository(str(tmp_path / "execution.db"))


def test_same_event_id_with_conflicting_payload_is_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        assert repo.apply_event(
            "event-1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=5, price=100.0, event_sequence=10
        )
        with pytest.raises(ValueError, match="conflicting execution payload"):
            repo.apply_event(
                "event-1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=4, price=100.0, event_sequence=10
            )
        assert repo.get_order(order_id)["filled_quantity"] == 5
        assert repo.snapshot().positions[(1, "zerodha", "NIFTY")] == 5
    finally:
        repo.close()


def test_same_event_id_with_conflicting_kind_is_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        assert repo.apply_event("event-1", order_id, "SUBMITTED", broker_account_id=1, broker_route="zerodha", event_sequence=20)
        with pytest.raises(ValueError, match="conflicting execution payload"):
            repo.apply_event("event-1", order_id, "CANCELLED", broker_account_id=1, broker_route="zerodha", event_sequence=20)
        assert repo.get_order(order_id)["status"] == "SUBMITTED"
    finally:
        repo.close()


def test_same_event_id_replay_remains_idempotent_when_payload_matches(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        assert repo.apply_event(
            "event-1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=5, price=100.0, event_sequence=30
        )
        assert not repo.apply_event(
            "event-1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=5, price=100.0, event_sequence=30
        )
        assert repo.get_order(order_id)["filled_quantity"] == 5
    finally:
        repo.close()


def test_same_event_id_replay_cannot_bypass_account_scope(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        assert repo.apply_event("event-1", order_id, "SUBMITTED", broker_account_id=1, broker_route="zerodha", event_sequence=40)
        with pytest.raises(ValueError, match="broker account identity mismatch"):
            repo.apply_event("event-1", order_id, "SUBMITTED", broker_account_id=2, broker_route="zerodha", event_sequence=40)
        assert repo.get_order(order_id)["status"] == "SUBMITTED"
    finally:
        repo.close()
