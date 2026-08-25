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
