from app.execution_health import ExecutionHealth, ExecutionHealthSnapshot
from app.execution_health_dto import ExecutionHealthDTO
from app.execution_observability import ExecutionObservability


def test_snapshot_serializes_to_stable_json_safe_dict():
    snapshot = ExecutionHealthSnapshot(1, 1, 0, 0, 0, 0, 0, 12.5, 8.0, True, True, 0.0)
    payload = ExecutionHealthDTO.from_snapshot(snapshot)
    assert payload["submissions"] == 1
    assert payload["broker_average_latency_ms"] == 12.5
    assert payload["broker_healthy"] is True


def test_current_builds_payload_from_health_provider():
    payload = ExecutionHealthDTO.current(ExecutionHealth(ExecutionObservability()))
    assert payload["submissions"] == 0
    assert payload["quarantine_rate"] == 0.0
    assert payload["recovery_healthy"] is True
