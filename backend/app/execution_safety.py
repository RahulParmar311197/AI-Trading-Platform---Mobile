from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass(frozen=True)
class ReconciliationIssue:
    client_order_id: str
    issue: str
    severity: str = "ERROR"


@dataclass
class ExecutionSafetyState:
    kill_switch: bool = False
    last_reconciliation: datetime | None = None
    issues: list[ReconciliationIssue] = field(default_factory=list)


class ExecutionSafetyManager:
    """Central safety gate for broker reconciliation and emergency shutdown."""

    def __init__(self):
        self.state = ExecutionSafetyState()
        self._lock = Lock()

    def engage_kill_switch(self, reason: str = "manual emergency stop") -> None:
        with self._lock:
            self.state.kill_switch = True
            self.state.issues.append(ReconciliationIssue("SYSTEM", reason, "CRITICAL"))

    def release_kill_switch(self) -> None:
        with self._lock:
            self.state.kill_switch = False

    def can_submit(self) -> bool:
        with self._lock:
            return not self.state.kill_switch

    def reconcile(self, local_orders: dict[str, dict], broker_orders: list[dict]) -> list[ReconciliationIssue]:
        broker_by_client = {str(o.get("client_order_id")): o for o in broker_orders if o.get("client_order_id")}
        issues: list[ReconciliationIssue] = []
        for client_id, local in local_orders.items():
            remote = broker_by_client.get(client_id)
            if remote is None:
                issues.append(ReconciliationIssue(client_id, "local order missing at broker"))
                continue
            local_state = str(local.get("state", ""))
            remote_state = str(remote.get("state", ""))
            if local_state and remote_state and local_state != remote_state:
                issues.append(ReconciliationIssue(client_id, f"state mismatch local={local_state} broker={remote_state}"))
            local_qty = float(local.get("filled_quantity", 0) or 0)
            remote_qty = float(remote.get("filled_quantity", 0) or 0)
            if abs(local_qty - remote_qty) > 1e-9:
                issues.append(ReconciliationIssue(client_id, f"fill mismatch local={local_qty} broker={remote_qty}"))
        with self._lock:
            self.state.last_reconciliation = datetime.now(timezone.utc)
            self.state.issues = issues
        return issues
