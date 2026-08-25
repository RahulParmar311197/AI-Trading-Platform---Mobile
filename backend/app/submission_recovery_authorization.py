from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


RECOVERY_ROLES = frozenset({"recovery_operator", "admin"})


@dataclass(frozen=True)
class RecoveryApproval:
    operator_id: str
    role: str
    broker_account_id: int
    broker_route: str


class RecoveryAuthorizer(Protocol):
    def authorize(self, approval: RecoveryApproval) -> None: ...


class RoleAndScopeRecoveryAuthorizer:
    """Fail-closed domain authorization for broker submission recovery."""

    def authorize(self, approval: RecoveryApproval) -> None:
        if not approval.operator_id:
            raise PermissionError("recovery operator identity is required")
        if approval.role not in RECOVERY_ROLES:
            raise PermissionError("recovery role is not authorized")
        if approval.broker_account_id <= 0:
            raise PermissionError("valid broker account scope is required")
        if not approval.broker_route:
            raise PermissionError("broker route scope is required")
