from __future__ import annotations

from .sql_repository import ExecutionRepository


TERMINAL_RELEASE_STATES = frozenset({"REJECTED", "CANCELLED", "CANCELED", "FILLED"})


class ReservationSettlement:
    """Release pre-trade reservations only after a terminal broker state."""

    def __init__(self, repository: ExecutionRepository):
        self._repository = repository

    def apply(self, client_order_id: str, broker_status: str) -> bool:
        status = broker_status.strip().upper()
        if status not in TERMINAL_RELEASE_STATES:
            return False
        self._repository.release(client_order_id)
        self._repository.session.commit()
        return True
