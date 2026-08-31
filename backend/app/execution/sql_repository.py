from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.risk_reservation import RiskReservationRecord
from app.models.submission_intent import SubmissionIntentRecord


class ExecutionRepository:
    """Persistence boundary for broker-submission intent and risk reservations."""

    def __init__(self, session: Session):
        self.session = session

    def get_intent(self, client_order_id: str) -> SubmissionIntentRecord | None:
        return self.session.get(SubmissionIntentRecord, client_order_id)

    def create_intent(self, *, client_order_id: str, route: str, account_id: str | None,
                      symbol: str, side: str, quantity: float, request_fingerprint: str,
                      created_at: datetime | None = None) -> SubmissionIntentRecord:
        intent = SubmissionIntentRecord(
            client_order_id=client_order_id,
            route=route,
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            request_fingerprint=request_fingerprint,
            created_at=created_at or datetime.now(timezone.utc),
        )
        self.session.add(intent)
        self.session.flush()
        return intent

    def resolve_intent(self, client_order_id: str, broker_order_id: str, status: str | None = None) -> SubmissionIntentRecord:
        intent = self.session.get(SubmissionIntentRecord, client_order_id)
        if intent is None:
            raise KeyError(client_order_id)
        intent.broker_order_id = broker_order_id
        intent.broker_status = status
        intent.resolved_at = datetime.now(timezone.utc)
        self.session.flush()
        return intent

    def reserve(self, *, client_order_id: str, broker_account_id: str, broker_route: str,
                amount: float, created_at: datetime | None = None) -> RiskReservationRecord:
        existing = self.session.scalar(select(RiskReservationRecord).where(
            RiskReservationRecord.client_order_id == client_order_id
        ))
        if existing is not None:
            return existing
        reservation = RiskReservationRecord(
            reservation_id=str(uuid4()),
            client_order_id=client_order_id,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            amount=amount,
            status="RESERVED",
            created_at=created_at or datetime.now(timezone.utc),
        )
        self.session.add(reservation)
        self.session.flush()
        return reservation

    def release(self, client_order_id: str) -> None:
        reservation = self.session.scalar(select(RiskReservationRecord).where(
            RiskReservationRecord.client_order_id == client_order_id
        ))
        if reservation is not None and reservation.status != "RELEASED":
            reservation.status = "RELEASED"
            reservation.released_at = datetime.now(timezone.utc)
            self.session.flush()
