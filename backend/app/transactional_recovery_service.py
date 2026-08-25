from __future__ import annotations

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository


class TransactionalRecoveryService:
    """Approve recovery across execution and quarantine using one SQLite transaction."""

    def __init__(self, repository: TransactionalExecutionRepository, quarantine: ExecutionEventQuarantine) -> None:
        self.repository = repository
        self.quarantine = quarantine

    def approve_and_apply(self, *, quarantine_id: int, identity: OrderIdentity, event_id: str, event_kind: str, quantity: float, price: float | None = None, approver: str) -> bool:
        if not approver:
            raise ValueError("approver is required")
        if identity.broker_account_id is None or identity.broker_account_id <= 0 or not identity.broker_route:
            raise ValueError("broker account identity and route are required")
        db = self.repository._db
        # Serialize the quarantine object's own connection against this attached-db transaction.
        # Otherwise a concurrent quarantine()/pending()/resolve attempt could race the attached
        # connection and invalidate the recovery case between validation and resolution.
        with self.quarantine._lock:
            with self.repository._lock:
                alias = "recovery_quarantine"
                db.execute("ATTACH DATABASE ? AS recovery_quarantine", (self.quarantine.database_path,))
                try:
                    db.execute("BEGIN IMMEDIATE")
                    row = db.execute("SELECT event_id,broker,broker_order_id,status FROM recovery_quarantine.execution_event_quarantine WHERE id=?", (quarantine_id,)).fetchone()
                    if row is None:
                        raise KeyError(quarantine_id)
                    event_id_in_case, broker, broker_order_id, status = row
                    if status != "OPEN":
                        raise ValueError("recovery case is no longer open")
                    if event_id_in_case != event_id or broker != identity.broker or broker_order_id != identity.broker_order_id:
                        raise ValueError("recovery identity mismatch")
                    self.repository._bind_identity_tx(identity)
                    applied = self.repository._apply_event_tx(event_id, identity.client_order_id, event_kind, broker_account_id=identity.broker_account_id, broker_route=identity.broker_route, price=price, quantity=quantity)
                    updated = db.execute("UPDATE recovery_quarantine.execution_event_quarantine SET status='RESOLVED' WHERE id=? AND status='OPEN'", (quarantine_id,)).rowcount
                    if updated != 1:
                        raise RuntimeError("recovery case changed during approval")
                    db.commit()
                    return applied
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.execute("DETACH DATABASE recovery_quarantine")
