from __future__ import annotations

from app.auth.session import UserSession


class NotificationHealthAuthorization:
    """User-facing notification health is read-only; operator actions stay service-token protected."""

    allowed_roles = frozenset({"user", "trader", "admin", "operator"})
    operator_roles = frozenset({"admin", "operator"})

    @classmethod
    def can_read_health(cls, session: UserSession) -> bool:
        return session.role in cls.allowed_roles

    @classmethod
    def can_operate_delivery(cls, session: UserSession) -> bool:
        return session.role in cls.operator_roles
