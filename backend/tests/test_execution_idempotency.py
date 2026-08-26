from app.execution import OrderStatus, execute_paper
from app.idempotency import InMemoryIdempotencyStore


def _risk():
    from app.order_intent import OrderIntent
    from app.risk_gateway import RiskGatewayResult

    order = OrderIntent(
        symbol="NIFTY",
        side="BUY",
        entry=25000,
        stop_loss=24900,
        take_profit=25200,
        quantity=1,
        risk_amount=100,
        source="test",
    )
    return RiskGatewayResult(approved=True, order=order, reasons=())


def test_execution_rejects_duplicate_request_before_second_fill():
    store = InMemoryIdempotencyStore()
    risk = _risk()
    first = execute_paper(
        risk=risk,
        account_id="paper-1",
        request_id="req-1",
        idempotency_store=store,
    )
    second = execute_paper(
        risk=risk,
        account_id="paper-1",
        request_id="req-1",
        idempotency_store=store,
    )
    assert first.status is OrderStatus.FILLED
    assert second.status is OrderStatus.DUPLICATE
    assert second.filled_quantity == 0
