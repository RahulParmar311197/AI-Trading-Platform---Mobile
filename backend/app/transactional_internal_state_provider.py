from __future__ import annotations

from app.internal_trading_state_provider import InternalTradingState, InternalTradingStateProvider
from app.transactional_execution_repository import TransactionalExecutionRepository


class TransactionalInternalTradingStateProvider(InternalTradingStateProvider):
    """Read-only adapter exposing account-safe transactional execution state."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def get_state(self) -> InternalTradingState:
        snapshot = self.repository.snapshot()
        account_scopes = {(account_id, route) for account_id, route, _symbol in snapshot.positions}
        if len(account_scopes) > 1:
            raise RuntimeError(
                "transactional execution state contains multiple broker accounts; "
                "request an account-scoped state view before pre-trade use"
            )
        positions = {symbol: float(quantity) for (_account_id, _route, symbol), quantity in snapshot.positions.items()}
        return InternalTradingState(
            positions=positions,
            open_order_ids=frozenset(snapshot.open_order_ids),
        )

    def get_state_for_account(self, *, broker_account_id: int, broker_route: str) -> InternalTradingState:
        if broker_account_id <= 0:
            raise ValueError("broker_account_id must be positive")
        if not broker_route:
            raise ValueError("broker_route is required")
        snapshot = self.repository.snapshot()
        positions = {
            symbol: float(quantity)
            for (account_id, route, symbol), quantity in snapshot.positions.items()
            if account_id == broker_account_id and route == broker_route
        }
        # ExecutionSnapshot exposes open orders only by ID. Resolve those IDs
        # against the durable order table while holding the repository lock so
        # an account-scoped risk view cannot inherit another account's orders.
        with self.repository._lock:
            rows = self.repository._db.execute(
                "SELECT order_id FROM orders "
                "WHERE status IN ('SUBMITTED','PARTIALLY_FILLED') "
                "AND broker_account_id=? AND broker_route=?",
                (broker_account_id, broker_route),
            ).fetchall()
        open_order_ids = frozenset(row[0] for row in rows)
        return InternalTradingState(
            positions=positions,
            open_order_ids=open_order_ids,
        )
