from __future__ import annotations

from dataclasses import dataclass

from app.execution_lifecycle import ExecutionLedger, OrderStatus
from app.execution_transaction_journal import ExecutionJournalEntry, ExecutionTransactionJournal


@dataclass(frozen=True)
class JournaledExecutionResult:
    applied: bool
    order_status: str
    event_id: str


class JournaledExecutionAdapter:
    """Coordinates execution ledger mutations with the durable execution journal."""

    def __init__(self, ledger: ExecutionLedger, journal: ExecutionTransactionJournal) -> None:
        self.ledger = ledger
        self.journal = journal

    def apply_fill(self, *, event_id: str, order_id: str, price: float, quantity: float) -> JournaledExecutionResult:
        if not event_id:
            raise ValueError("event_id is required")
        order = self.ledger.orders[order_id]
        if self.journal.apply(ExecutionJournalEntry(
            event_id=event_id,
            order_id=order_id,
            event_kind="FILL",
            position_symbol=order.symbol,
            position_delta=quantity if order.side == "BUY" else -quantity,
            payload={"price": price, "quantity": quantity},
        )) is False:
            return JournaledExecutionResult(False, order.status.value, event_id)
        updated = self.ledger.fill(order_id, price, quantity)
        return JournaledExecutionResult(True, updated.status.value, event_id)

    def transition(self, *, event_id: str, order_id: str, status: OrderStatus) -> JournaledExecutionResult:
        if self.journal.apply(ExecutionJournalEntry(
            event_id=event_id, order_id=order_id, event_kind=status.value,
            position_symbol=None, position_delta=0.0, payload={"status": status.value},
        )) is False:
            return JournaledExecutionResult(False, self.ledger.orders[order_id].status.value, event_id)
        updated = self.ledger.transition(order_id, status)
        return JournaledExecutionResult(True, updated.status.value, event_id)
