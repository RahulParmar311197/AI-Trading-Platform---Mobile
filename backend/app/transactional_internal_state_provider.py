from __future__ import annotations

from app.internal_trading_state_provider import InternalTradingState, InternalTradingStateProvider
from app.transactional_execution_repository import TransactionalExecutionRepository


class TransactionalInternalTradingStateProvider(InternalTradingStateProvider):
    """Read-only adapter making the transactional execution repository the pre-trade state source."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def get_state(self) -> InternalTradingState:
        snapshot = self.repository.snapshot()
        return InternalTradingState(
            positions=dict(snapshot.positions),
            open_order_ids=frozenset(snapshot.open_order_ids),
        )
