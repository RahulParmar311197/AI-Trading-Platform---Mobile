import pytest

from app.execution_event_quarantine import ExecutionEventQuarantine


def test_direct_quarantine_resolution_is_forbidden(tmp_path):
    quarantine = ExecutionEventQuarantine(str(tmp_path / "quarantine.db"))
    quarantine.quarantine(
        event_id="evt-1",
        broker="upstox",
        broker_order_id="broker-1",
        payload={"broker_account_id": 1, "broker_route": "primary"},
        reason="MANUAL_REVIEW",
    )
    case_id = quarantine.list_recovery_cases()[0]["id"]
    with pytest.raises(RuntimeError, match="direct quarantine resolution is disabled"):
        quarantine.resolve(case_id)
    assert quarantine.list_recovery_cases()[0]["status"] == "OPEN"
    quarantine.close()
