from __future__ import annotations

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository


class TransactionalRecoveryService:
    """Approve a recovery case only through one atomic execution/reconciliation boundary."""

    def __init__(self, repository: TransactionalExecutionRepository, quarantine: ExecutionEventQuarantine) -> None:
        self.repository = repository
        self.quarantine = quarantine

    def approve_and_apply(self, *, quarantine_id: int, identity: OrderIdentity, event_id: str, event_kind: str, quantity: float, price: float | None = None, approver: str) -> bool:
        if not approver:
            raise ValueError("approver is required")
        with self.quarantine._lock:
            self.quarantine._db.execute("BEGIN IMMEDIATE")
            try:
                row = self.quarantine._db.execute("SELECT event_id,broker,broker_order_id,payload,status FROM execution_event_quarantine WHERE id=?", (quarantine_id,)).fetchone()
                if row is None:
                    raise KeyError(quarantine_id)
                event_id_in_case, broker, broker_order_id, payload, status = row
                if status != "OPEN":
                    raise ValueError("recovery case is no longer open")
                if event_id_in_case != event_id or broker != identity.broker or broker_order_id != identity.broker_order_id:
                    raise ValueError("recovery identity mismatch")
                if identity.broker_account_id is None or not identity.broker_route:
                    raise ValueError("broker account identity and route are required")
                self.repository._bind_identity_tx(identity)
                applied = self.repository._apply_event_tx(event_id, identity.client_order_id, event_kind, broker_account_id=identity.broker_account_id, broker_route=identity.broker_route, price=price, quantity=quantity)
                self.quarantine._db.execute("UPDATE execution_event_quarantine SET status='RESOLVED' WHERE id=? AND status='OPEN'", (quarantine_id,))
                if self.quarantine._db.execute("SELECT changes()").fetchone()[0] != 1:
                    raise RuntimeError("recovery case changed during approval")
                self.quarantine._db.commit()
                self.repository._db.commit()
                return applied
            except Exception:
                self.quarantine._db.rollback()
                self.repository._db.rollback()
                raise
