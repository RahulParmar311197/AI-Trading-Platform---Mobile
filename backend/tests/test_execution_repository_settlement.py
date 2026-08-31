from types import SimpleNamespace

from app.execution.sql_repository import ExecutionRepository


class Session:
    def __init__(self, reservation):
        self.reservation = reservation
        self.flush_calls = 0

    def scalar(self, _query):
        return self.reservation

    def flush(self):
        self.flush_calls += 1


def test_settle_from_broker_status_releases_terminal_reservation_without_commit():
    reservation = SimpleNamespace(status="RESERVED", released_at=None)
    session = Session(reservation)

    settled = ExecutionRepository(session).settle_from_broker_status("client-1", " filled ")

    assert settled is True
    assert reservation.status == "RELEASED"
    assert reservation.released_at is not None
    assert session.flush_calls == 1


def test_settle_from_broker_status_keeps_non_terminal_reservation():
    reservation = SimpleNamespace(status="RESERVED", released_at=None)
    session = Session(reservation)

    settled = ExecutionRepository(session).settle_from_broker_status("client-1", "PARTIALLY_FILLED")

    assert settled is False
    assert reservation.status == "RESERVED"
    assert reservation.released_at is None
    assert session.flush_calls == 0


def test_settle_from_broker_status_is_idempotent_for_released_reservation():
    reservation = SimpleNamespace(status="RELEASED", released_at="already-set")
    session = Session(reservation)

    settled = ExecutionRepository(session).settle_from_broker_status("client-1", "CANCELLED")

    assert settled is True
    assert reservation.status == "RELEASED"
    assert reservation.released_at == "already-set"
    assert session.flush_calls == 0
