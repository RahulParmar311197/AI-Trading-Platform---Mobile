import math

import pytest

from app.api.orders import _project_authoritative_broker_update
from app.broker_adapter import BrokerOrderUpdate
from app.models import Order


def make_order() -> Order:
    return Order(
        id=1,
        user_id=1,
        broker_account_id=7,
        broker_route="paper:account:7",
        broker_route_generation="gen-1",
        client_order_id="cancel-projection",
        symbol="ABC",
        side="BUY",
        quantity=10,
        status="PARTIALLY_FILLED",
        filled_quantity=2,
    )


def test_cancel_projection_persists_authoritative_fill_and_average_price():
    order = make_order()
    result = BrokerOrderUpdate(
        order_id="BROKER-1",
        status="FILLED",
        filled_quantity=10,
        average_price=101.25,
    )

    _project_authoritative_broker_update(order, result)

    assert order.filled_quantity == 10
    assert order.average_fill_price == 101.25


def test_cancel_projection_keeps_existing_fill_when_broker_omits_fill_fields():
    order = make_order()
    result = BrokerOrderUpdate(order_id="BROKER-1", status="CANCELLED")

    _project_authoritative_broker_update(order, result)

    assert order.filled_quantity == 2
    assert order.average_fill_price is None


@pytest.mark.parametrize("filled", [-1, 11, math.inf, math.nan])
def test_cancel_projection_rejects_invalid_authoritative_fill(filled):
    order = make_order()
    result = BrokerOrderUpdate(
        order_id="BROKER-1",
        status="FILLED",
        filled_quantity=filled,
        average_price=101.25,
    )

    with pytest.raises(ValueError, match="fill quantity is invalid"):
        _project_authoritative_broker_update(order, result)


def test_cancel_projection_rejects_non_finite_average_price():
    order = make_order()
    result = BrokerOrderUpdate(
        order_id="BROKER-1",
        status="FILLED",
        filled_quantity=10,
        average_price=math.inf,
    )

    with pytest.raises(ValueError, match="average price is invalid"):
        _project_authoritative_broker_update(order, result)
