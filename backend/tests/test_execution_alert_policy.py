from app.execution_alert_policy import ExecutionAlertPolicy
from app.execution_alert_store import ExecutionAlertStore
from app.execution_health import ExecutionHealth, ExecutionHealthStatus
from app.execution_observability import ExecutionObservability


def snapshot_with_failure():
    metrics = ExecutionObservability()
    metrics.increment("submissions")
    metrics.increment("broker_failures")
    return ExecutionHealth(metrics).snapshot()


def snapshot_with_high_latency():
    metrics = ExecutionObservability()
    metrics.observe_latency("broker_latency", 6000)
    return ExecutionHealth(metrics).snapshot()


def test_repeated_same_alert_is_deduplicated_during_cooldown():
    policy = ExecutionAlertPolicy(cooldown_seconds=300)
    snapshot = snapshot_with_high_latency()
    assert policy.evaluate(snapshot, now=1000) is not None
    assert policy.evaluate(snapshot, now=1100) is None
    assert policy.evaluate(snapshot, now=1301) is not None


def test_critical_escalation_bypasses_degraded_cooldown():
    policy = ExecutionAlertPolicy(cooldown_seconds=300)
    degraded = snapshot_with_high_latency()
    critical = snapshot_with_failure()
    assert degraded.status is ExecutionHealthStatus.DEGRADED
    assert critical.status is ExecutionHealthStatus.CRITICAL
    assert policy.evaluate(degraded, now=1000) is not None
    assert policy.evaluate(critical, now=1001) is not None


def test_healthy_state_does_not_generate_alert():
    policy = ExecutionAlertPolicy()
    healthy = ExecutionHealth(ExecutionObservability()).snapshot()
    assert policy.evaluate(healthy, now=1000) is None


def test_durable_store_prevents_duplicate_after_policy_restart(tmp_path):
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    snapshot = snapshot_with_high_latency()

    first = ExecutionAlertPolicy(cooldown_seconds=300, store=store)
    second = ExecutionAlertPolicy(cooldown_seconds=300, store=store)

    assert first.evaluate(snapshot, now=1000) is not None
    assert second.evaluate(snapshot, now=1100) is None
    assert len(store.recent()) == 1


def test_durable_store_allows_alert_after_cooldown(tmp_path):
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    snapshot = snapshot_with_high_latency()
    policy = ExecutionAlertPolicy(cooldown_seconds=300, store=store)

    assert policy.evaluate(snapshot, now=1000) is not None
    assert policy.evaluate(snapshot, now=1301) is not None
    assert len(store.recent()) == 2


def test_durable_store_preserves_critical_escalation(tmp_path):
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    policy = ExecutionAlertPolicy(cooldown_seconds=300, store=store)
    degraded = snapshot_with_high_latency()
    critical = snapshot_with_failure()

    assert policy.evaluate(degraded, now=1000) is not None
    assert policy.evaluate(critical, now=1001) is not None
    assert len(store.recent()) == 2
