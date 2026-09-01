import pytest

from app.brokers.dhan import DhanAdapter


@pytest.mark.parametrize(
    "method,args",
    [
        ("get_positions", ()),
        ("get_orders", ()),
        ("get_order", ("order-1",)),
        ("get_trades", ()),
        ("get_trades_for_order", ("order-1",)),
    ],
)
def test_unconfigured_dhan_snapshot_methods_fail_closed(method, args):
    adapter = DhanAdapter({})

    with pytest.raises(RuntimeError, match="credentials are not configured"):
        getattr(adapter, method)(*args)


def test_unconfigured_dhan_health_is_non_ready_not_empty_snapshot():
    adapter = DhanAdapter({})

    health = adapter.health()

    assert health == {
        "broker": "dhan",
        "configured": False,
        "authenticated": False,
        "live_trading_enabled": False,
    }
