from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.risk_reservation import RiskReservationRecord


class DBRiskReservationProvider:
    """Canonical DB-backed reservation provider for live execution."""

    def __init__(self, session: Session):
        self.session = session

    def reserve(self, *, client_order_id: str, broker_account_id: str,
                broker_route: str, amount: float) -> str:
        if amount < 0:
            raise ValueError("reservation amount must be non-negative")
        existing = self.session.scalar(
            select(RiskReservationRecord).where(
                RiskReservationRecord.client_order_id == client_order_id
            )
        )
        if existing is not None:
            if existing.broker_account_id != broker_account_id or existing.broker_route != broker_route or existing.amount != amount:
                raise ValueError("client_order_id is already bound to a different reservation")
            return existing.reservation_id

        reservation = RiskReservationRecord(
            reservation_id=str(uuid4()),
            client_order_id=client_order_id,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            amount=amount,
            status="RESERVED",
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(reservation)
        self.session.flush()
        return reservation.reservation_id

    def release(self, reservation_id: str) -> None:
        reservation = self.session.get(RiskReservationRecord, reservation_id)
        if reservation is None:
            return
        if reservation.status != "RELEASED":
            reservation.status = "RELEASED"
            reservation.released_at = datetime.now(timezone.utc)
            self.session.flush()
