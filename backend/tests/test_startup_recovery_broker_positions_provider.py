from app.startup_recovery import RecoveryState, StartupRecoveryCoordinator


def test_recovery_requires_broker_position_snapshot():
    recovery = StartupRecoveryCoordinator()
    result = recovery.recover(type("L", (), {"orders": {}, "positions": {}})(), lambda order: None)
    assert result.state == RecoveryState.FAILED
    assert "position snapshot unavailable" in (result.reason or "")


def test_recovery_uses_provider_and_reaches_ready_on_match():
    recovery = StartupRecoveryCoordinator()
    lifecycle = type("L", (), {"orders": {}, "positions": {}})()
    result = recovery.recover(lifecycle, lambda order: None, broker_positions_provider=lambda: [])
    assert result.state == RecoveryState.READY
    assert recovery.execution_allowed


def test_provider_mismatch_keeps_execution_locked():
    class Position:
        quantity = 10
        side = "BUY"
    lifecycle = type("L", (), {"orders": {}, "positions": {"NIFTY": Position()}})()
    recovery = StartupRecoveryCoordinator()
    result = recovery.recover(lifecycle, lambda order: None, broker_positions_provider=lambda: [{"symbol": "NIFTY", "side": "BUY", "quantity": 9}])
    assert result.state == RecoveryState.FAILED
    assert not recovery.execution_allowed
    assert result.position_mismatches
