from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import uuid
from typing import Callable

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

from app.models.risk_reservation import RiskReservationRecord


class RiskReservationStore:
    """Cross-worker durable exposure reservations."""

    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    TERMINAL = {"FILLED", "CANCELLED", "REJECTED"}

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
                            released_at=None,
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

    def reconcile(self, *, reservation_id: str, broker_status: str, remaining_amount: float | None = None) -> str:
        """Idempotently reconcile a reservation from authoritative broker state."""
        rid = str(reservation_id).strip()
        if not rid:
            raise ValueError("reservation_id is required")
        status = str(broker_status or "").strip().upper().replace("-", "_").replace(" ", "_")
        session = self._session_factory()
        try:
            with session.begin():
                record = session.get(RiskReservationRecord, rid)
                if record is None:
                    raise KeyError(rid)
                if record.status == self.RELEASED:
                    return self.RELEASED
                # Reserve and partial-fill updates must serialize on the same
                # account/route scope; otherwise a stale partial-fill worker
                # could overwrite a newer, smaller reservation.
                self._lock_scope(session, self._scope(record.broker_account_id, record.broker_route))
                if status in self.TERMINAL:
                    record.status = self.RELEASED
                    record.released_at = datetime.now(timezone.utc)
                    return self.RELEASED
                if status != self.PARTIALLY_FILLED:
                    raise RuntimeError("ambiguous broker state cannot release risk reservation")
                if remaining_amount is None:
                    raise ValueError("remaining_amount is required for partial fill reconciliation")
                remaining = self._decimal(remaining_amount, "remaining_amount")
                if remaining < 0:
                    raise ValueError("remaining_amount cannot be negative")
                current = self._decimal(record.amount, "reservation amount")
                if remaining > current:
                    raise RuntimeError("partial fill reconciliation cannot increase risk reservation")
                if remaining == 0:
                    record.status = self.RELEASED
                    record.released_at = datetime.now(timezone.utc)
                    return self.RELEASED
                record.amount = remaining
                return self.ACTIVE
        finally:
            session.close()

    def reconcile_client_order(self, *, client_order_id: str, broker_status: str, remaining_amount: float | None = None) -> str | None:
        """Reconcile the reservation bound to a client order, if one exists."""
        client_id = str(client_order_id).strip()
        if not client_id:
            raise ValueError("client_order_id is required")
        session = self._session_factory()
        try:
            record = session.query(RiskReservationRecord).filter_by(client_order_id=client_id).one_or_none()
            if record is None:
                return None
            reservation_id = record.reservation_id
        finally:
            session.close()
        return self.reconcile(
            reservation_id=reservation_id,
            broker_status=broker_status,
            remaining_amount=remaining_amount,
        )

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
