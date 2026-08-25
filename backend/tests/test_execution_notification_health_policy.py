from datetime import datetime, timedelta, timezone

from app.execution_notification_health_policy import NotificationHealthPolicy


def test_healthy_when_worker_recent_and_no_threshold_breaches():
    recent = datetime.now(timezone.utc).isoformat()
    status, reasons = NotificationHealthPolicy().evaluate("RUNNING", recent, 0, 0)
    assert status == "HEALTHY"
    assert reasons == []


def test_worker_stopped_is_degraded():
    status, reasons = NotificationHealthPolicy().evaluate("STOPPED", None, 0, 0)
    assert status == "DEGRADED"
    assert "WORKER_STOPPED" in reasons
    assert "NO_SUCCESSFUL_HEARTBEAT" in reasons


def test_stale_heartbeat_is_degraded():
    old = (datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()
    status, reasons = NotificationHealthPolicy(stale_after_seconds=30).evaluate("RUNNING", old, 0, 0)
    assert status == "DEGRADED"
    assert "STALE_HEARTBEAT" in reasons


def test_invalid_heartbeat_is_degraded():
    status, reasons = NotificationHealthPolicy().evaluate("RUNNING", "not-a-date", 0, 0)
    assert status == "DEGRADED"
    assert "INVALID_HEARTBEAT" in reasons


def test_backlog_and_dead_letters_are_degraded():
    recent = datetime.now(timezone.utc).isoformat()
    policy = NotificationHealthPolicy(pending_threshold=10, dead_letter_threshold=1)
    status, reasons = policy.evaluate("RUNNING", recent, 10, 1)
    assert status == "DEGRADED"
    assert "OUTBOX_BACKLOG" in reasons
    assert "DEAD_LETTER_EVENTS" in reasons
