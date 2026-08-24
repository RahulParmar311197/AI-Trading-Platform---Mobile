from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.execution_authorization import ExecutionAuthorization
from app.safety_state import SafetyStateStore
from app.session_baseline import SessionBaselineStore
from app.session_risk import SessionPolicy
from app.session_risk_gate import SessionRiskGate


@dataclass(frozen=True)
class Snapshot:
    timestamp: datetime
    current_equity: float
    realized_daily_pnl: float


def build(tmp_path, snapshot):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    baseline = SessionBaselineStore(str(tmp_path / "baseline.json"))
    session_gate = SessionRiskGate(baseline, SessionPolicy(block_after_daily_loss_percent=3.0))
    return ExecutionAuthorization(safety, session_risk_gate=session_gate, session_clock=lambda _: snapshot)


def test_session_loss_blocks_before_general_risk_gate(tmp_path):
    ts = datetime(2026, 8, 24, 9, 15, tzinfo=timezone.utc)
    auth = build(tmp_path, Snapshot(ts, 97000, -3000))
    # First call establishes the baseline; the second call must be blocked at 3%.
    assert auth.check(object()).allowed
    result = auth.check(object())
    assert not result.allowed
    assert result.code == "SESSION_RISK_REJECTED"


def test_session_gate_fails_closed_when_clock_missing(tmp_path):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    baseline = SessionBaselineStore(str(tmp_path / "baseline.json"))
    auth = ExecutionAuthorization(safety, session_risk_gate=SessionRiskGate(baseline))
    result = auth.check(object())
    assert not result.allowed
    assert result.code == "SESSION_CLOCK_UNAVAILABLE"
