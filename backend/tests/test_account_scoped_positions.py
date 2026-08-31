from __future__ import annotations

import json

import pytest

from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle, OrderStatus


def test_fill_creates_account_scoped_position() -> None:
    lifecycle = OrderLifecycle()
    order = lifecycle.create(
        "o-1", "RELIANCE", "BUY", 10,
        broker_account_id="acct-a", broker_route="broker:account:acct-a:g1",
    )

    lifecycle.apply_fill(order.order_id, 10, 2500.0, fill_id="fill-1")

    position = lifecycle.positions["RELIANCE"]
    assert position.broker_account_id == "acct-a"
    assert position.broker_route == "broker:account:acct-a:g1"


def test_cross_account_position_mutation_is_rejected() -> None:
    lifecycle = OrderLifecycle()
    lifecycle.create(
        "o-a", "RELIANCE", "BUY", 10,
        broker_account_id="acct-a", broker_route="broker:account:acct-a:g1",
    )
    lifecycle.apply_fill("o-a", 10, 2500.0, fill_id="fill-a")

    lifecycle.create(
        "o-b", "RELIANCE", "BUY", 5,
        broker_account_id="acct-b", broker_route="broker:account:acct-b:g1",
    )

    with pytest.raises(ValueError, match="position broker account context mismatch"):
        lifecycle.apply_fill("o-b", 5, 2510.0, fill_id="fill-b")


def test_position_account_context_survives_atomic_persistence(tmp_path) -> None:
    path = tmp_path / "execution_state.json"
    lifecycle = OrderLifecycle()
    lifecycle.create(
        "o-1", "TCS", "BUY", 2,
        broker_account_id="acct-a", broker_route="broker:account:acct-a:g7",
    )
    lifecycle.apply_fill("o-1", 2, 4000.0, fill_id="fill-1")

    store = ExecutionStateStore(str(path))
    store.save(lifecycle)

    restored = OrderLifecycle()
    assert store.load(restored) is True
    position = restored.positions["TCS"]
    assert position.broker_account_id == "acct-a"
    assert position.broker_route == "broker:account:acct-a:g7"


def test_v2_position_state_migrates_as_explicitly_unscoped(tmp_path) -> None:
    path = tmp_path / "execution_state.json"
    legacy = {
        "schema_version": 2,
        "orders": {},
        "positions": {
            "INFY": {
                "symbol": "INFY",
                "side": "BUY",
                "quantity": 1,
                "entry_price": 1500.0,
                "status": "OPEN",
                "exit_price": None,
                "realized_pnl": 0.0,
            }
        },
        "realized_pnl_by_symbol": {},
        "realized_pnl_by_day": {},
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")

    lifecycle = OrderLifecycle()
    assert ExecutionStateStore(str(path)).load(lifecycle) is True
    position = lifecycle.positions["INFY"]
    assert position.broker_account_id is None
    assert position.broker_route is None


def test_account_context_is_preserved_when_position_is_reversed() -> None:
    lifecycle = OrderLifecycle()
    lifecycle.create(
        "buy", "SBIN", "BUY", 10,
        broker_account_id="acct-a", broker_route="broker:account:acct-a:g1",
    )
    lifecycle.apply_fill("buy", 10, 800.0, fill_id="buy-fill")

    lifecycle.create(
        "sell", "SBIN", "SELL", 15,
        broker_account_id="acct-a", broker_route="broker:account:acct-a:g1",
    )
    lifecycle.apply_fill("sell", 15, 810.0, fill_id="sell-fill")

    position = lifecycle.positions["SBIN"]
    assert position.side == "SELL"
    assert position.quantity == 5
    assert position.broker_account_id == "acct-a"
    assert position.broker_route == "broker:account:acct-a:g1"
