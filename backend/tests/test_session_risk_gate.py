from datetime import datetime, timezone

from app.session_baseline import SessionBaselineStore
from app.session_risk_gate import SessionRiskGate
from app.session_risk import SessionPolicy


def test_baseline_is_created_once_and_reused(tmp_path):
    store = SessionBaselineStore(str(tmp_path / "baseline.json"))
    gate = SessionRiskGate(store)
    ts = datetime(2026, 8, 24, 9, 15, tzinfo=timezone.utc)
    first = gate.evaluate(ts, 100000, 0)
    second = gate.evaluate(ts, 95000, -1000)
    assert first.allowed
    assert second.allowed
    assert second.session_start_equity == 100000


def test_daily_loss_lock_uses_persisted_baseline(tmp_path):
    store = SessionBaselineStore(str(tmp_path / "baseline.json"))
    gate = SessionRiskGate(store, SessionPolicy(block_after_daily_loss_percent=3.0))
    ts = datetime(2026, 8, 24, 9, 15, tzinfo=timezone.utc)
    gate.evaluate(ts, 100000, 0)
    blocked = gate.evaluate(ts, 95000, -3000)
    assert not blocked.allowed
    assert blocked.reason == "daily loss lock active"
    assert blocked.session_start_equity == 100000


def test_next_day_gets_new_baseline(tmp_path):
    store = SessionBaselineStore(str(tmp_path / "baseline.json"))
    gate = SessionRiskGate(store)
    first = gate.evaluate(datetime(2026, 8, 24, 9, 15, tzinfo=timezone.utc), 100000, 0)
    second = gate.evaluate(datetime(2026, 8, 25, 9, 15, tzinfo=timezone.utc), 98000, 0)
    assert first.session_start_equity == 100000
    assert second.session_start_equity == 98000
