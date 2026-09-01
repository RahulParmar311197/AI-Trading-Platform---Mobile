from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    ACTIVE_BROKER_STATUSES = {"NEW", "SUBMITTED", "OPEN", "ACCEPTED", "PENDING", "PENDING_NEW", "TRIGGER_PENDING", "PARTIALLY_FILLED"}

    def __init__(self, session_factory: Callable[[], object]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _scope(account_id: str, route: str) -> str:
        account = str(account_id).strip(); broker_route = str(route).strip()
        if not account or not broker_route: raise ValueError("broker account and route are required")
        return f"{account}\x1f{broker_route}"

    @staticmethod
    def _decimal(value: float, name: str) -> Decimal:
        try: parsed = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc: raise ValueError(f"{name} must be finite and numeric") from exc
        if not parsed.is_finite(): raise ValueError(f"{name} must be finite and numeric")
        return parsed

    @staticmethod
    def _lock_scope(session: object, scope: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"), {"scope": scope})

    def reserve(self, *, reservation_id: str | None, client_order_id: str, broker_account_id: str, broker_route: str, amount: float, current_exposure: float, max_total_exposure: float) -> str:
        client_order_id = str(client_order_id).strip()
        if not client_order_id: raise ValueError("client_order_id is required")
        amount_d = self._decimal(amount, "amount"); current_d = self._decimal(current_exposure, "current_exposure"); limit_d = self._decimal(max_total_exposure, "max_total_exposure")
        if amount_d <= 0 or current_d < 0 or limit_d < 0: raise ValueError("risk reservation values must be non-negative and amount must be positive")
        if current_d + amount_d > limit_d: raise RuntimeError("risk reservation exceeds exposure limit")
        scope = self._scope(broker_account_id, broker_route); account = str(broker_account_id).strip(); route = str(broker_route).strip(); rid = str(reservation_id or uuid.uuid4()).strip()
        if not rid: raise ValueError("reservation_id is required")
        session = self._session_factory()
        try:
            with session.begin():
                self._lock_scope(session, scope)
                existing = session.query(RiskReservationRecord).filter_by(client_order_id=client_order_id).one_or_none()
                if existing is not None and existing.status == self.ACTIVE:
                    if existing.broker_account_id != account or existing.broker_route != route or self._decimal(existing.amount, "existing reservation") != amount_d:
                        raise RuntimeError("active risk reservation already exists for client order")
                    return existing.reservation_id
                reserved = session.query(func.coalesce(func.sum(RiskReservationRecord.amount), 0)).filter(RiskReservationRecord.broker_account_id == account, RiskReservationRecord.broker_route == route, RiskReservationRecord.status == self.ACTIVE).scalar()
                reserved_d = self._decimal(reserved or 0, "active reservations")
                if current_d + reserved_d + amount_d > limit_d: raise RuntimeError("risk reservation exceeds concurrent exposure limit")
                now = datetime.now(timezone.utc)
                if existing is not None:
                    existing.reservation_id = rid; existing.broker_account_id = account; existing.broker_route = route; existing.amount = amount_d; existing.status = self.ACTIVE; existing.created_at = now; existing.released_at = None
                else:
                    session.add(RiskReservationRecord(reservation_id=rid, client_order_id=client_order_id, broker_account_id=account, broker_route=route, amount=amount_d, status=self.ACTIVE, created_at=now, released_at=None))
                session.flush(); return rid
        except IntegrityError as exc:
            raise RuntimeError("risk reservation could not be created safely") from exc
        finally: session.close()

    def release(self, reservation_id: str) -> None:
        reservation_id = str(reservation_id).strip()
        if not reservation_id: raise ValueError("reservation_id is required")
        session = self._session_factory()
        try:
            with session.begin():
                record = session.get(RiskReservationRecord, reservation_id)
                if record is None: raise KeyError(reservation_id)
                if record.status == self.ACTIVE:
                    record.status = self.RELEASED; record.released_at = datetime.now(timezone.utc)
        finally: session.close()

    def reconcile(self, *, reservation_id: str, broker_status: str, remaining_amount: float | None = None) -> str:
        rid = str(reservation_id).strip()
        if not rid: raise ValueError("reservation_id is required")
        status = str(broker_status or "").strip().upper().replace("-", "_").replace(" ", "_")
        session = self._session_factory()
        try:
            with session.begin():
                record = session.get(RiskReservationRecord, rid)
                if record is None: raise KeyError(rid)
                if record.status == self.RELEASED: return self.RELEASED
                self._lock_scope(session, self._scope(record.broker_account_id, record.broker_route))
                if status in self.TERMINAL:
                    record.status = self.RELEASED; record.released_at = datetime.now(timezone.utc); return self.RELEASED
                if status != self.PARTIALLY_FILLED: raise RuntimeError("ambiguous broker state cannot release risk reservation")
                if remaining_amount is None: raise ValueError("remaining_amount is required for partial fill reconciliation")
                remaining = self._decimal(remaining_amount, "remaining_amount")
                if remaining < 0: raise ValueError("remaining_amount cannot be negative")
                current = self._decimal(record.amount, "reservation amount")
                if remaining > current: raise RuntimeError("partial fill reconciliation cannot increase risk reservation")
                if remaining == 0:
                    record.status = self.RELEASED; record.released_at = datetime.now(timezone.utc); return self.RELEASED
                record.amount = remaining; return self.ACTIVE
        finally: session.close()

    def reconcile_client_order(self, *, client_order_id: str, broker_status: str, remaining_amount: float | None = None) -> str | None:
        client_id = str(client_order_id).strip()
        if not client_id: raise ValueError("client_order_id is required")
        session = self._session_factory()
        try:
            record = session.query(RiskReservationRecord).filter_by(client_order_id=client_id).one_or_none()
            if record is None: return None
            reservation_id = record.reservation_id
        finally: session.close()
        return self.reconcile(reservation_id=reservation_id, broker_status=broker_status, remaining_amount=remaining_amount)

    def stale_active_reservations(self, *, max_age: timedelta, as_of: datetime | None = None, broker_account_id: str | None = None, broker_route: str | None = None) -> list[dict]:
        """Return stale ACTIVE reservations; age alone never releases risk."""
        if max_age.total_seconds() < 0: raise ValueError("max_age cannot be negative")
        now = as_of or datetime.now(timezone.utc)
        if now.tzinfo is None: raise ValueError("as_of must be timezone-aware")
        account = str(broker_account_id).strip() if broker_account_id is not None else None
        route = str(broker_route).strip() if broker_route is not None else None
        if account is not None and not account: raise ValueError("broker_account_id cannot be empty")
        if route is not None and not route: raise ValueError("broker_route cannot be empty")
        cutoff = now - max_age
        session = self._session_factory()
        try:
            query = session.query(RiskReservationRecord).filter(RiskReservationRecord.status == self.ACTIVE, RiskReservationRecord.created_at <= cutoff)
            if account is not None: query = query.filter(RiskReservationRecord.broker_account_id == account)
            if route is not None: query = query.filter(RiskReservationRecord.broker_route == route)
            records = query.order_by(RiskReservationRecord.created_at.asc()).all()
            return [{"reservation_id": r.reservation_id, "client_order_id": r.client_order_id, "broker_account_id": r.broker_account_id, "broker_route": r.broker_route, "amount": float(r.amount), "created_at": r.created_at, "age_seconds": max(0.0, (now-r.created_at).total_seconds()), "reason": "STALE_RISK_RESERVATION_REQUIRES_BROKER_RECONCILIATION"} for r in records]
        finally: session.close()

    def recover_stale_reservations(self, *, broker_orders: list[dict], broker_account_id: str, broker_route: str, max_age: timedelta, as_of: datetime | None = None) -> dict:
        """Recover stale reservations only through the authoritative broker snapshot.

        Age is a recovery trigger, never a release decision. Any validation
        failure leaves every reservation unchanged because the authoritative
        reconciler applies mutations only after validating the complete scope.
        """
        account = str(broker_account_id).strip(); route = str(broker_route).strip()
        candidates = self.stale_active_reservations(max_age=max_age, as_of=as_of, broker_account_id=account, broker_route=route)
        if not candidates:
            return {"candidates": [], "failures": [], "reconciled_reservation_ids": []}
        failures = self.reconcile_authoritative_orders(broker_orders=broker_orders, broker_account_id=account, broker_route=route)
        if failures:
            return {"candidates": candidates, "failures": failures, "reconciled_reservation_ids": []}
        session = self._session_factory()
        try:
            reconciled_ids = []
            for candidate in candidates:
                record = session.get(RiskReservationRecord, candidate["reservation_id"])
                if record is None or record.status != self.ACTIVE:
                    reconciled_ids.append(candidate["reservation_id"])
            return {"candidates": candidates, "failures": [], "reconciled_reservation_ids": reconciled_ids}
        finally: session.close()

    def reconcile_authoritative_orders(self, *, broker_orders: list[dict], broker_account_id: str, broker_route: str) -> list[dict]:
        """Reconcile every active reservation against one authoritative broker snapshot."""
        account = str(broker_account_id).strip(); route = str(broker_route).strip(); scope = self._scope(account, route)
        by_client: dict[str, list[dict]] = {}
        for order in broker_orders:
            if not isinstance(order, dict): continue
            client_id = str(order.get("client_order_id") or "").strip()
            if client_id: by_client.setdefault(client_id, []).append(order)
        session = self._session_factory()
        try:
            with session.begin():
                self._lock_scope(session, scope)
                records = session.query(RiskReservationRecord).filter(RiskReservationRecord.broker_account_id == account, RiskReservationRecord.broker_route == route, RiskReservationRecord.status == self.ACTIVE).all()
                active_clients = {record.client_order_id for record in records}; failures = []
                for client_id, matches in by_client.items():
                    if client_id not in active_clients:
                        active_matches = [m for m in matches if str(m.get("status") or "").strip().upper().replace("-", "_").replace(" ", "_") in self.ACTIVE_BROKER_STATUSES]
                        if active_matches: failures.append({"id": client_id, "reason": "RISK_RESERVATION_ORPHAN_BROKER_ORDER"})
                planned = []
                for record in records:
                    matches = by_client.get(record.client_order_id, [])
                    if len(matches) != 1:
                        failures.append({"id": record.client_order_id, "reason": "RISK_RESERVATION_BROKER_MATCH_MISSING" if not matches else "RISK_RESERVATION_BROKER_MATCH_AMBIGUOUS"}); continue
                    broker = matches[0]; status = str(broker.get("status") or "").strip().upper().replace("-", "_").replace(" ", "_")
                    if status in self.TERMINAL: planned.append((record, status, None)); continue
                    if status not in self.ACTIVE_BROKER_STATUSES:
                        failures.append({"id": record.client_order_id, "reason": "RISK_RESERVATION_BROKER_STATE_AMBIGUOUS"}); continue
                    if status != self.PARTIALLY_FILLED: planned.append((record, status, None)); continue
                    quantity = broker.get("quantity", broker.get("requested_quantity")); filled = broker.get("filled_quantity", broker.get("filledQty", broker.get("filled_qty")))
                    try: quantity_d = self._decimal(quantity, "broker quantity"); filled_d = self._decimal(filled, "broker filled quantity")
                    except ValueError:
                        failures.append({"id": record.client_order_id, "reason": "RISK_RESERVATION_PARTIAL_FILL_FACTS_MISSING"}); continue
                    if quantity_d < 0 or filled_d < 0 or filled_d > quantity_d:
                        failures.append({"id": record.client_order_id, "reason": "RISK_RESERVATION_PARTIAL_FILL_FACTS_INVALID"}); continue
                    remaining = quantity_d - filled_d; current = self._decimal(record.amount, "reservation amount")
                    if remaining > current:
                        failures.append({"id": record.client_order_id, "reason": "RISK_RESERVATION_PARTIAL_FILL_INCREASE"}); continue
                    planned.append((record, status, remaining))
                if failures: return failures
                now = datetime.now(timezone.utc)
                for record, status, remaining in planned:
                    if status in self.TERMINAL or remaining == 0:
                        record.status = self.RELEASED; record.released_at = now
                    elif status == self.PARTIALLY_FILLED and remaining is not None: record.amount = remaining
                return []
        finally: session.close()

    def active_amount(self, *, broker_account_id: str, broker_route: str) -> float:
        account = str(broker_account_id).strip(); route = str(broker_route).strip(); self._scope(account, route)
        session = self._session_factory()
        try:
            value = session.query(func.coalesce(func.sum(RiskReservationRecord.amount), 0)).filter(RiskReservationRecord.broker_account_id == account, RiskReservationRecord.broker_route == route, RiskReservationRecord.status == self.ACTIVE).scalar()
            return float(value or 0)
        finally: session.close()
