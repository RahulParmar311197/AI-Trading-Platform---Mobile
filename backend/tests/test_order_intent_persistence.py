from __future__ import annotations

import pytest

from app.api.orders import _commit_execution_intent, _commit_execution_projection


class FakeOrder:
    client_order_id = "client-123"


class RecordingSession:
    def __init__(self, fail: bool = False):
        self.events: list[str] = []
        self.fail = fail

    def commit(self) -> None:
        self.events.append("commit")
        if self.fail:
            raise RuntimeError("db unavailable")

    def refresh(self, order) -> None:
        self.events.append("refresh")

    def rollback(self) -> None:
        self.events.append("rollback")


def test_execution_intent_commits_before_refresh() -> None:
    session = RecordingSession()
    order = FakeOrder()

    _commit_execution_intent(session, order)

    assert session.events == ["commit", "refresh"]


def test_execution_intent_failure_rolls_back_and_never_refreshes() -> None:
    session = RecordingSession(fail=True)

    with pytest.raises(Exception) as exc_info:
        _commit_execution_intent(session, FakeOrder())

    assert "ORDER_INTENT_PERSISTENCE_FAILED" in str(exc_info.value)
    assert session.events == ["commit", "rollback"]


def test_execution_projection_commits_before_refresh() -> None:
    session = RecordingSession()

    _commit_execution_projection(session, FakeOrder())

    assert session.events == ["commit", "refresh"]


def test_execution_projection_failure_fails_closed_for_reconciliation() -> None:
    session = RecordingSession(fail=True)

    with pytest.raises(Exception) as exc_info:
        _commit_execution_projection(session, FakeOrder())

    error = exc_info.value
    assert "EXECUTION_PROJECTION_PERSISTENCE_FAILED" in str(error)
    assert "reconciliation_required" in str(error)
    assert session.events == ["commit", "rollback"]
