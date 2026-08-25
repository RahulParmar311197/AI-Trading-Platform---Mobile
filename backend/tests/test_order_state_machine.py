import pytest

from app.order_state_machine import InvalidOrderTransition, OrderState, OrderStateMachine


def test_normal_fill_path():
    machine = OrderStateMachine()
    assert machine.transition(OrderState.SUBMITTING) == OrderState.SUBMITTING
    assert machine.transition(OrderState.OPEN) == OrderState.OPEN
    assert machine.transition(OrderState.PARTIALLY_FILLED) == OrderState.PARTIALLY_FILLED
    assert machine.transition(OrderState.FILLED) == OrderState.FILLED
    assert machine.terminal is True


def test_ambiguous_submission_enters_reconciliation():
    machine = OrderStateMachine()
    machine.transition(OrderState.SUBMITTING)
    machine.transition(OrderState.PENDING_RECONCILIATION)
    assert machine.state == OrderState.PENDING_RECONCILIATION
    assert machine.terminal is False


def test_reconciliation_can_resolve_to_existing_order_state():
    machine = OrderStateMachine(OrderState.PENDING_RECONCILIATION)
    assert machine.transition(OrderState.OPEN) == OrderState.OPEN


@pytest.mark.parametrize("target", [OrderState.SUBMITTING, OrderState.OPEN, OrderState.FILLED])
def test_terminal_state_cannot_transition(target):
    machine = OrderStateMachine(OrderState.FILLED)
    with pytest.raises(InvalidOrderTransition):
        machine.transition(target)


def test_created_order_cannot_jump_to_filled():
    machine = OrderStateMachine()
    with pytest.raises(InvalidOrderTransition):
        machine.transition(OrderState.FILLED)
