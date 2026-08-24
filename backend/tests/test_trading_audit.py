import json

from app.trading_audit import TradingAuditLog


def test_audit_log_appends_structured_events(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = TradingAuditLog(str(path))
    audit.record("STARTUP_STATE_CHANGE", from_state="RECOVERING", to_state="READY")
    audit.record("EMERGENCY_HALT", reason="broker anomaly", actor="admin")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["event_type"] == "STARTUP_STATE_CHANGE"
    assert rows[1]["reason"] == "broker anomaly"
