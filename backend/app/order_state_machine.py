from __future__ import annotations

from enum import Enum


class OrderState(str, Enum):
    CREATED = "CREATED"
    SUBMITTING = "SUBMITTING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"


_ALLOWED: dict[OrderState, set[OrderState]] = {
    OrderState.CREATED: {OrderState.SUBMITTING, OrderState.REJECTED},
    OrderState.SUBMITTING: {
        OrderState.OPEN,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.REJECTED,
        OrderState.PENDING_RECONCILIATION,
    },
    OrderState.OPEN: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING,
        OrderState.PENDING_RECONCILIATION,
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING,
        OrderState.PENDING_RECONCILIATION,
    },
    OrderState.FILLED: set(),
    OrderState.CANCEL_PENDING: {
        OrderState.CANCELLED,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.PENDING_RECONCILIATION,
    },
    OrderState.CANCELLED: set(),
    OrderState.REJECTED: set(),
    OrderState.PENDING_RECONCILIATION: {
        OrderState.OPEN,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.PENDING_RECONCILIATION,
    },
}


class InvalidOrderTransition(ValueError):
    pass


class OrderStateMachine:
    """Explicit fail-closed order transitions; ambiguous broker states reconcile first."""

    def __init__(self, initial: OrderState = OrderState.CREATED):
        self.state = initial

    def transition(self, target: OrderState) -> OrderState:
        if target not in _ALLOWED[self.state]:
            raise InvalidOrderTransition(f"invalid order transition: {self.state.value} -> {target.value}")
        self.state = target
        return self.state

    def can_transition(self, target: OrderState) -> bool:
        return target in _ALLOWED[self.state]

    @property
    def terminal(self) -> bool:
        return self.state in {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED}
