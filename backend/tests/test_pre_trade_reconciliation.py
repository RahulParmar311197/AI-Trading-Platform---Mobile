from __future__ import annotations

import pytest

from app.broker_reconciliation import reconcile_positions
from app.pre_trade_reconciliation_gate import (
    PreTradeReconciliationError,
    PreTradeReconciliationGate,
    PreTradeReconciliationPolicy,
)


def test_matching_positions_allow_trade() -> None:
    report = PreTradeReconciliationGate().check(
        [{"symbol": "NIFTY", "quantity": 2}],
        [{"symbol": "NIFTY", "quantity": 2}],
    )
    assert report.matched
    assert report.deltas == ()


def test_quantity_mismatch_blocks_trade() -> None:
    with pytest.raises(PreTradeReconciliationError, match="position mismatch"):
        PreTradeReconciliationGate().check(
            [{"symbol": "NIFTY", "quantity": 2}],
            [{"symbol": "NIFTY", "quantity": 3}],
        )


def test_broker_only_and_local_only_are_reported() -> None:
    report = reconcile_positions(
        [{"symbol": "NIFTY", "quantity": 2}],
        [{"symbol": "BANKNIFTY", "quantity": 1}],
    )
    assert report.matched is False
    assert report.local_only == ("NIFTY",)
    assert report.broker_only == ("BANKNIFTY",)


def test_tolerance_is_respected() -> None:
    report = reconcile_positions(
        [{"symbol": "NIFTY", "quantity": 2}],
        [{"symbol": "NIFTY", "quantity": 2.01}],
        quantity_tolerance=0.01,
    )
    assert report.matched


def test_disabled_gate_does_not_block() -> None:
    report = PreTradeReconciliationGate(
        PreTradeReconciliationPolicy(enabled=False)
    ).check(
        [{"symbol": "NIFTY", "quantity": 2}],
        [{"symbol": "NIFTY", "quantity": 99}],
    )
    assert report.matched


def test_invalid_position_quantity_fails_closed() -> None:
    with pytest.raises(ValueError, match="invalid quantity"):
        reconcile_positions(
            [{"symbol": "NIFTY", "quantity": "not-a-number"}],
            [],
        )
