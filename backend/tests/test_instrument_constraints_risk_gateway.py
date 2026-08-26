from app.instrument_constraints import InstrumentConstraints
from app.order_intent import OrderIntent
from app.risk_gateway import authorize


def test_risk_gateway_normalizes_price_and_quantity_before_exposure_check():
    constraints = InstrumentConstraints(
        tick_size=0.05,
        quantity_step=1.0,
        min_quantity=1.0,
    )
    order = OrderIntent(
        'NIFTY',
        'BUY',
        100.07,
        90.02,
        120.09,
        3.9,
        50.0,
        'strategy',
        0.9,
        constraints,
    )

    result = authorize(
        order=order,
        equity=10000,
        daily_pnl=0,
        open_positions=0,
    )

    assert result.approved
    assert result.order.entry == 100.05
    assert result.order.stop_loss == 90.0
    assert result.order.take_profit == 120.05
    assert result.order.quantity == 3.0
    assert result.decision.exposure == 300.15


def test_risk_gateway_rejects_order_that_becomes_invalid_after_tick_normalization():
    constraints = InstrumentConstraints(tick_size=1.0, quantity_step=1.0)
    order = OrderIntent(
        'NIFTY',
        'BUY',
        100.4,
        100.2,
        100.6,
        1.0,
        10.0,
        'strategy',
        0.9,
        constraints,
    )

    try:
        authorize(order=order, equity=10000, daily_pnl=0, open_positions=0)
    except ValueError as exc:
        assert 'BUY requires stop < entry < target' in str(exc)
    else:
        raise AssertionError('normalized invalid order must be rejected before risk approval')
