from pathlib import Path

import pytest

from app.execution_lifecycle import OrderStatus
from app.transactional_execution_repository import TransactionalExecutionRepository


def make_repo(tmp_path: Path) -> TransactionalExecutionRepository:
    return TransactionalExecutionRepository(str(tmp_path / "execution.db"))


def test_stale_sequence_is_rejected_without_mutating_order_or_position(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        assert repo.apply_event("e1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=5, event_sequence=10)
        with pytest.raises(ValueError, match="stale execution event sequence"):
            repo.apply_event("e0", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=1, event_sequence=9)
        order = repo.get_order(order_id)
        assert order["filled_quantity"] == 5
        assert order["status"] == OrderStatus.PARTIALLY_FILLED.value
        assert repo.snapshot().positions[(1, "zerodha", "NIFTY")] == 5
    finally:
        repo.close()


def test_equal_sequence_is_rejected_even_with_a_new_event_id(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        repo.apply_event("e1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=5, event_sequence=20)
        with pytest.raises(ValueError, match="sequence already consumed"):
            repo.apply_event("e2", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=5, event_sequence=20)
        assert repo.get_order(order_id)["filled_quantity"] == 5
    finally:
        repo.close()


def test_same_event_id_with_conflicting_sequence_is_rejected(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        assert repo.apply_event("e1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=5, event_sequence=30)
        with pytest.raises(ValueError, match="already bound"):
            repo.apply_event("e1", order_id, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=1, event_sequence=31)
        assert repo.get_order(order_id)["filled_quantity"] == 5
    finally:
        repo.close()


def test_sequence_cursor_is_scoped_to_account_and_route(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    try:
        first = repo.create_order("NIFTY", "BUY", 10, broker_account_id=1, broker_route="zerodha")
        second = repo.create_order("NIFTY", "BUY", 10, broker_account_id=2, broker_route="zerodha")
        assert repo.apply_event("a1", first, "PARTIAL_FILL", broker_account_id=1, broker_route="zerodha", quantity=5, event_sequence=1)
        assert repo.apply_event("b1", second, "PARTIAL_FILL", broker_account_id=2, broker_route="zerodha", quantity=5, event_sequence=1)
        assert repo.get_order(first)["filled_quantity"] == 5
        assert repo.get_order(second)["filled_quantity"] == 5
    finally:
        repo.close()
