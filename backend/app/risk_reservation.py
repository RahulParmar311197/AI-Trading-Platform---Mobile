from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.risk_reservation import RiskReservationRecord


class DBRiskReservationProvider:
    """Canonical DB-backed reservation provider for live execution."""

    def __init__(self, session: Session):
        self.session = session

    def reserve(
        self,
        *,
        reservation_id: str | None,
        client_order_id: str,
        broker_account_id: str,
        broker_route: str,
        amount: float,
        current_exposure: float,
        max_total_exposure: float,
    ) -> str:
        if amount <= 0:
            raise ValueError("reservation amount must be positive")
        if current_exposure < 0 or max_total_exposure < 0:
            raise ValueError("exposure values must be non-negative")
        if current_exposure + amount > max_total_exposure:
            raise ValueError("risk reservation would exceed maximum total exposure")

        existing = self.session.scalar(
            select(RiskReservationRecord).where(
                RiskReservationRecord.client_order_id == client_order_id
            )
        )
        if existing is not None:
            if reservation_id is not None and existing.reservation_id != reservation_id:
                raise ValueError("reservation_id does not match client_order_id")
            if (
                existing.broker_account_id != broker_account_id
                or existing.broker_route != broker_route
                or float(existing.amount) != float(amount)
            ):
                raise ValueError("client_order_id is already bound to a different reservation")
            if existing.status == "RELEASED":
                raise ValueError("client_order_id was already released")
            return existing.reservation_id

        if reservation_id is not None:
            if self.session.get(RiskReservationRecord, reservation_id) is not None:
                raise ValueError("reservation_id is already in use")

        active_reserved = self.session.scalar(
            select(func.coalesce(func.sum(RiskReservationRecord.amount), 0)).where(
                RiskReservationRecord.broker_account_id == broker_account_id,
                RiskReservationRecord.broker_route == broker_route,
                RiskReservationRecord.status == "RESERVED",
            )
        )
        if current_exposure + float(active_reserved or 0) + amount > max_total_exposure:
            raise ValueError("active reservations would exceed maximum total exposure")

        reservation = RiskReservationRecord(
            reservation_id=reservation_id or str(uuid4()),
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
        if reservation is None or reservation.status == "RELEASED":
            return
        reservation.status = "RELEASED"
        reservation.released_at = datetime.now(timezone.utc)
        self.session.flush()
