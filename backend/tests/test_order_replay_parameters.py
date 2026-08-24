from __future__ import annotations

from app.api.orders import _broker_request
from app.models import Order


def test_broker_request_preserves_limit_execution_parameters_on_replay() -> None:
    order = Order(
        user_id=42,
        client_order_id="cid-1",
        symbol="NIFTY",
        side="BUY",
        quantity=2,
        order_type="LIMIT",
        price=22500.25,
        stop=None,
        security_id="NIFTY-SEC-1",
        status="PENDING",
    )

    request = _broker_request(
        order.client_order_id,
        order.symbol,
        order.side,
        order.quantity,
        order.order_type,
        order.price,
        order.stop,
        order.security_id,
        order.user_id,
    )

    assert request.order_type == "LIMIT"
    assert request.price == 22500.25
    assert request.stop is None
    assert request.security_id == "NIFTY-SEC-1"
    assert request.owner_user_id == 42


def test_order_model_persists_execution_parameters() -> None:
    assert {"price", "stop", "security_id"}.issubset(Order.__table__.columns.keys())
    assert Order.__table__.c.price.nullable is True
    assert Order.__table__.c.stop.nullable is True
    assert Order.__table__.c.security_id.nullable is False
