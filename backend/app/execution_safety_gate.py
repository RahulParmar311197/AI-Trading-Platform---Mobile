from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionBlockReason(str, Enum):
    EMERGENCY_HALT = "EMERGENCY_HALT"
    RECONCILIATION_NOT_READY = "RECONCILIATION_NOT_READY"
    BROKER_UNHEALTHY = "BROKER_UNHEALTHY"
    RISK_LIMIT_BREACH = "RISK_LIMIT_BREACH"
    INVALID_SCOPE = "INVALID_SCOPE"


@dataclass(frozen=True)
class ExecutionSafetyContext:
    emergency_halt: bool
    reconciliation_ready: bool
    broker_healthy: bool
    risk_allowed: bool
    broker_account_id: int | None
    broker_route: str | None


@dataclass(frozen=True)
class ExecutionAuthorization:
    allowed: bool
    reason: ExecutionBlockReason | None = None


class ExecutionSafetyGate:
    """Fail-closed authorization boundary immediately before broker execution."""

    def authorize(self, context: ExecutionSafetyContext) -> ExecutionAuthorization:
        if context.emergency_halt:
            return ExecutionAuthorization(False, ExecutionBlockReason.EMERGENCY_HALT)
        if not context.reconciliation_ready:
            return ExecutionAuthorization(False, ExecutionBlockReason.RECONCILIATION_NOT_READY)
        if not context.broker_healthy:
            return ExecutionAuthorization(False, ExecutionBlockReason.BROKER_UNHEALTHY)
        if not context.risk_allowed:
            return ExecutionAuthorization(False, ExecutionBlockReason.RISK_LIMIT_BREACH)
        if context.broker_account_id is None or not context.broker_route:
            return ExecutionAuthorization(False, ExecutionBlockReason.INVALID_SCOPE)
        return ExecutionAuthorization(True)
