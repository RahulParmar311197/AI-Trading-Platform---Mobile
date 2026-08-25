from app.execution_observability import ExecutionObservability


def test_execution_metrics_increment_and_snapshot():
    metrics = ExecutionObservability()
    metrics.increment("submissions")
    metrics.increment("submitted")
    metrics.increment("duplicate_preventions", 2)
    snapshot = metrics.snapshot()
    assert snapshot.submissions == 1
    assert snapshot.submitted == 1
    assert snapshot.duplicate_preventions == 2
    assert snapshot.quarantined == 0


def test_invalid_metric_is_rejected():
    metrics = ExecutionObservability()
    try:
        metrics.increment("unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_scoped_metrics_do_not_cross_contaminate_accounts():
    metrics = ExecutionObservability()
    metrics.increment_scoped("submissions", 7, "upstox:account:7", 3)
    metrics.increment_scoped("broker_failures", 8, "upstox:account:8")
    metrics.observe_latency_scoped("broker_latency", 7, "upstox:account:7", 120.0)

    account_7 = metrics.snapshot_scoped(7, "upstox:account:7")
    account_8 = metrics.snapshot_scoped(8, "upstox:account:8")

    assert account_7.submissions == 3
    assert account_7.broker_failures == 0
    assert account_7.broker_latency_ms_total == 120.0
    assert account_8.submissions == 0
    assert account_8.broker_failures == 1
    assert account_8.broker_latency_ms_total == 0.0


def test_scoped_metrics_are_separate_from_platform_aggregate():
    metrics = ExecutionObservability()
    metrics.increment("submissions", 2)
    metrics.increment_scoped("submissions", 7, "upstox:account:7")

    assert metrics.snapshot().submissions == 2
    assert metrics.snapshot_scoped(7, "upstox:account:7").submissions == 1


def test_invalid_scoped_identity_is_rejected():
    metrics = ExecutionObservability()
    try:
        metrics.increment_scoped("submissions", 0, "upstox:account:0")
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid broker account id to fail")

    try:
        metrics.increment_scoped("submissions", 7, "")
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid broker route to fail")
