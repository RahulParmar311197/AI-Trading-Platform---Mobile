from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.risk_reservation import RiskReservationRecord


class ExecutionRepository:
    """Small SQL execution-state adapter for terminal broker settlement."""

    TERMINAL_STATUSES = {"FILLED", "CANCELLED", "REJECTED"}

    def __init__(self, session) -> None:
        self._session = session

    def settle_from_broker_status(self, client_order_id: str, broker_status: str) -> bool:
        client_id = str(client_order_id).strip()
        status = str(broker_status or "").strip().upper().replace("-", "_").replace(" ", "_")
        if not client_id:
            raise ValueError("client_order_id is required")
        if not status:
            raise ValueError("broker_status is required")
        if status not in self.TERMINAL_STATUSES:
            return False

        reservation = self._session.scalar(
            select(RiskReservationRecord).where(RiskReservationRecord.client_order_id == client_id)
        )
        if reservation is None:
            return False
        if reservation.status == "RELEASED":
            return True
        reservation.status = "RELEASED"
        reservation.released_at = datetime.now(timezone.utc)
        self._session.flush()
        return True
