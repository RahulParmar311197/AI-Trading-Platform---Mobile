from app.order_lifecycle import OrderLifecycle


def test_order_lifecycle_preserves_opaque_broker_account_ids():
    lifecycle = OrderLifecycle()
    first = lifecycle.create(
        "client-001",
        "NIFTY",
        "BUY",
        1,
        broker_account_id="001",
        broker_route="upstox",
    )
    second = lifecycle.create(
        "client-1",
        "NIFTY",
        "BUY",
        1,
        broker_account_id="1",
        broker_route="upstox",
    )

    assert first.broker_account_id == "001"
    assert second.broker_account_id == "1"
    assert first.broker_account_id != second.broker_account_id


def test_order_lifecycle_rejects_empty_broker_account_id():
    lifecycle = OrderLifecycle()

    try:
        lifecycle.create(
            "client-empty",
            "NIFTY",
            "BUY",
            1,
            broker_account_id="   ",
            broker_route="upstox",
        )
    except ValueError as exc:
        assert str(exc) == "broker_account_id must not be empty"
    else:
        raise AssertionError("empty broker account identity must fail closed")
