from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import uuid
from typing import Callable

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

from app.models.risk_reservation import RiskReservationRecord


class RiskReservationStore:
    """Cross-worker durable exposure reservations.

    PostgreSQL uses a transaction-scoped advisory lock per account/route so the
    active-reservation sum and insert are one serialized decision. SQLite is
    supported for unit tests only; production configuration must use a server
    database, where the advisory lock provides the cross-process guarantee.
    """

    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"

    def __init__(self, session_factory: Callable[[], object]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _scope(account_id: str, route: str) -> str:
        account = str(account_id).strip()
        broker_route = str(route).strip()
        if not account or not broker_route:
            raise ValueError("broker account and route are required")
        return f"{account}\x1f{broker_route}"

    @staticmethod
    def _decimal(value: float, name: str) -> Decimal:
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"{name} must be finite and numeric") from exc
        if not parsed.is_finite():
            raise ValueError(f"{name} must be finite and numeric")
        return parsed

    @staticmethod
    def _lock_scope(session: object, scope: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                {"scope": scope},
            )

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
        """Atomically reserve exposure or fail closed.

        ``current_exposure`` is the authoritative broker snapshot exposure;
        active reservations represent approved orders not yet reflected there.
        The combined amount may not exceed ``max_total_exposure``.
        """
        client_order_id = str(client_order_id).strip()
        if not client_order_id:
            raise ValueError("client_order_id is required")
        amount_d = self._decimal(amount, "amount")
        current_d = self._decimal(current_exposure, "current_exposure")
        limit_d = self._decimal(max_total_exposure, "max_total_exposure")
        if amount_d <= 0 or current_d < 0 or limit_d < 0:
            raise ValueError("risk reservation values must be non-negative and amount must be positive")
        if current_d + amount_d > limit_d:
            raise RuntimeError("risk reservation exceeds exposure limit")
        scope = self._scope(broker_account_id, broker_route)
        account = str(broker_account_id).strip()
        route = str(broker_route).strip()
        rid = str(reservation_id or uuid.uuid4()).strip()
        if not rid:
            raise ValueError("reservation_id is required")
        session = self._session_factory()
        try:
            with session.begin():
                self._lock_scope(session, scope)
                existing = session.query(RiskReservationRecord).filter_by(client_order_id=client_order_id).one_or_none()
                if existing is not None and existing.status == self.ACTIVE:
                    raise RuntimeError("active risk reservation already exists for client order")
                reserved = session.query(func.coalesce(func.sum(RiskReservationRecord.amount), 0)).filter(
                    RiskReservationRecord.broker_account_id == account,
                    RiskReservationRecord.broker_route == route,
                    RiskReservationRecord.status == self.ACTIVE,
                ).scalar()
                reserved_d = self._decimal(reserved or 0, "active reservations")
                if current_d + reserved_d + amount_d > limit_d:
                    raise RuntimeError("risk reservation exceeds concurrent exposure limit")
                now = datetime.now(timezone.utc)
                if existing is not None:
                    existing.reservation_id = rid
                    existing.broker_account_id = account
                    existing.broker_route = route
                    existing.amount = amount_d
                    existing.status = self.ACTIVE
                    existing.created_at = now
                    existing.released_at = None
                else:
                    session.add(
                        RiskReservationRecord(
                            reservation_id=rid,
                            client_order_id=client_order_id,
                            broker_account_id=account,
                            broker_route=route,
                            amount=amount_d,
                            status=self.ACTIVE,
                            created_at=now,
                        )
                    )
                session.flush()
                return rid
        except IntegrityError as exc:
            raise RuntimeError("risk reservation could not be created safely") from exc
        finally:
            session.close()

    def release(self, reservation_id: str) -> None:
        reservation_id = str(reservation_id).strip()
        if not reservation_id:
            raise ValueError("reservation_id is required")
        session = self._session_factory()
        try:
            with session.begin():
                record = session.get(RiskReservationRecord, reservation_id)
                if record is None:
                    raise KeyError(reservation_id)
                if record.status == self.ACTIVE:
                    record.status = self.RELEASED
                    record.released_at = datetime.now(timezone.utc)
        finally:
            session.close()

    def active_amount(self, *, broker_account_id: str, broker_route: str) -> float:
        account = str(broker_account_id).strip()
        route = str(broker_route).strip()
        self._scope(account, route)
        session = self._session_factory()
        try:
            value = session.query(func.coalesce(func.sum(RiskReservationRecord.amount), 0)).filter(
                RiskReservationRecord.broker_account_id == account,
                RiskReservationRecord.broker_route == route,
                RiskReservationRecord.status == self.ACTIVE,
            ).scalar()
            return float(value or 0)
        finally:
            session.close()
