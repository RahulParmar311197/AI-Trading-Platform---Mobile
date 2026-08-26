from datetime import datetime, timezone

import pytest

from app.reconciliation import ReconciliationEngine, ReconciliationCheckResult


def test_failed_check_cannot_create_verified_result():
    engine = ReconciliationEngine()
    check = engine.check(
        [{"client_order_id": "c1", "status": "FILLED", "quantity": 1, "filled_quantity": 1}],
        [],
        [],
        [],
    )
    assert check.ok is False
    with pytest.raises(ValueError, match="failed reconciliation"):
        engine.build_verified_result(
            check,
            account_id="acct-1",
            generation=1,
            reconciled_at=datetime.now(timezone.utc),
            open_orders_reconciled=True,
            positions_reconciled=True,
            submission_intents_resolved=0,
            broker_ready=True,
            broker_snapshot_fingerprint="fp-1",
        )


def test_check_result_cannot_be_manually_constructed():
    with pytest.raises(TypeError, match="ReconciliationEngine.check"):
        ReconciliationCheckResult(
            ok=True,
            trading_halted=False,
            order_drift=[],
            position_drift=[],
            checked_at="2026-08-26T18:00:00+00:00",
            _verification_token=object(),
        )


def test_successful_check_can_create_verified_result():
    engine = ReconciliationEngine()
    check = engine.check([], [], [], [])
    result = engine.build_verified_result(
        check,
        account_id="acct-1",
        generation=1,
        reconciled_at=datetime.now(timezone.utc),
        open_orders_reconciled=True,
        positions_reconciled=True,
        submission_intents_resolved=0,
        broker_ready=True,
        broker_snapshot_fingerprint="fp-1",
    )
    assert result.verified is True
    assert result.account_id == "acct-1"
