from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, create_engine, select, update


@dataclass(frozen=True)
class ReconciliationState:
    broker_account_id: int
    broker_route: str
    status: str
    trading_halted: bool
    checked_at: str | None
    order_drift_count: int
    position_drift_count: int


class ReconciliationStateStore:
    """Durable, account/route-scoped reconciliation safety state.

    Missing or stale state is deliberately treated as blocked by
    ``is_trading_blocked``. A process restart therefore cannot silently clear
    an unresolved or expired reconciliation halt.
    """

    def __init__(self, database_url: str | None = None, *, engine=None):
        if engine is None:
            if not database_url:
                raise ValueError("database_url or engine is required")
            engine = create_engine(database_url, pool_pre_ping=True)
        self.engine = engine
        self.metadata = MetaData()
        self.table = Table(
            "reconciliation_states",
            self.metadata,
            Column("broker_account_id", Integer, primary_key=True),
            Column("broker_route", String(160), primary_key=True),
            Column("status", String(32), nullable=False),
            Column("trading_halted", Boolean, nullable=False),
            Column("checked_at", String(64), nullable=True),
            Column("order_drift_count", Integer, nullable=False),
            Column("position_drift_count", Integer, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.metadata.create_all(self.engine, tables=[self.table])

    @staticmethod
    def _validate_scope(broker_account_id: int, broker_route: str) -> None:
        if isinstance(broker_account_id, bool) or broker_account_id <= 0:
            raise ValueError("positive broker_account_id is required")
        if not str(broker_route or "").strip():
            raise ValueError("broker_route is required")

    @staticmethod
    def _checked_at_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)

    def record_check(self, *, broker_account_id: int, broker_route: str, result) -> ReconciliationState:
        self._validate_scope(broker_account_id, broker_route)
        if not getattr(result, "verified", False):
            raise ValueError("authenticated reconciliation check is required")
        status = "VERIFIED" if result.ok else "HALTED"
        state = {
            "broker_account_id": broker_account_id,
            "broker_route": broker_route,
            "status": status,
            "trading_halted": not result.ok,
            "checked_at": result.checked_at,
            "order_drift_count": len(result.order_drift),
            "position_drift_count": len(result.position_drift),
            "updated_at": datetime.now(timezone.utc),
        }
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(self.table.c.broker_account_id).where(
                    self.table.c.broker_account_id == broker_account_id,
                    self.table.c.broker_route == broker_route,
                )
            ).first()
            if existing:
                connection.execute(
                    update(self.table)
                    .where(
                        self.table.c.broker_account_id == broker_account_id,
                        self.table.c.broker_route == broker_route,
                    )
                    .values(**state)
                )
            else:
                connection.execute(self.table.insert().values(**state))
        return ReconciliationState(
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            status=status,
            trading_halted=not result.ok,
            checked_at=result.checked_at,
            order_drift_count=len(result.order_drift),
            position_drift_count=len(result.position_drift),
        )

    def get_state(self, *, broker_account_id: int, broker_route: str) -> ReconciliationState:
        self._validate_scope(broker_account_id, broker_route)
        with self.engine.connect() as connection:
            row = connection.execute(
                select(self.table).where(
                    self.table.c.broker_account_id == broker_account_id,
                    self.table.c.broker_route == broker_route,
                )
            ).mappings().first()
        if row is None:
            return ReconciliationState(broker_account_id, broker_route, "UNKNOWN", True, None, 0, 0)
        return ReconciliationState(
            broker_account_id=int(row["broker_account_id"]),
            broker_route=row["broker_route"],
            status=row["status"],
            trading_halted=bool(row["trading_halted"]),
            checked_at=row["checked_at"],
            order_drift_count=int(row["order_drift_count"]),
            position_drift_count=int(row["position_drift_count"]),
        )

    def is_trading_blocked(
        self,
        *,
        broker_account_id: int,
        broker_route: str,
        max_age_seconds: float = 30.0,
    ) -> bool:
        self._validate_scope(broker_account_id, broker_route)
        try:
            max_age = float(max_age_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("max_age_seconds must be positive and finite") from exc
        if max_age <= 0 or max_age != max_age or max_age == float("inf") or max_age == float("-inf"):
            raise ValueError("max_age_seconds must be positive and finite")
        state = self.get_state(broker_account_id=broker_account_id, broker_route=broker_route)
        if state.trading_halted or state.status != "VERIFIED":
            return True
        checked_at = self._checked_at_datetime(state.checked_at)
        if checked_at is None:
            return True
        age = (datetime.now(timezone.utc) - checked_at).total_seconds()
        if age < 0:
            return True
        return age > max_age
