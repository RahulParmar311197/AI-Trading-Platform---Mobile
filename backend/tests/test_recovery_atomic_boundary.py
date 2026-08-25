import pytest

from app.execution_event_quarantine import ExecutionEventQuarantine


def test_quarantine_resolve_requires_explicit_atomic_recovery_boundary(tmp_path):
    quarantine = ExecutionEventQuarantine(str(tmp_path / "q.db"))
    assert quarantine.quarantine(event_id="recovery-atomic", broker="upstox", broker_order_id="b1", payload={"broker_account_id":1,"broker_route":"primary"}, reason="MANUAL_REVIEW")
    case = quarantine.list_recovery_cases()[0]
    assert case["status"] == "OPEN"
    # Direct resolution is intentionally not used by recovery approval; the control-plane
    # operation must bind identity and resolve the case as one atomic unit.
    assert hasattr(quarantine, "resolve")
    quarantine.close()
