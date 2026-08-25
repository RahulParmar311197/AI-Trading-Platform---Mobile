from fastapi.testclient import TestClient

from app.app_factory import create_app, create_resources


def build_client(tmp_path):
    resources = create_resources(
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.db"),
        safety_path=str(tmp_path / "safety.json"),
        audit_path=str(tmp_path / "audit.jsonl"),
        alert_path=str(tmp_path / "alerts.db"),
    )
    return TestClient(create_app(resources=resources)), resources


def test_acknowledge_and_resolve_alert(tmp_path):
    client, resources = build_client(tmp_path)
    alert = resources.execution_alert_store.record("CRITICAL", ("BROKER_FAILURE",), "CRITICAL:BROKER_FAILURE")
    headers = {"X-Execution-Health-Token": "test-token"}

    assert client.post(f"/execution/alerts/{alert.alert_id}/acknowledge", headers=headers).json()["status"] == "ACKNOWLEDGED"
    assert client.post(f"/execution/alerts/{alert.alert_id}/resolve", headers=headers).json()["status"] == "RESOLVED"


def test_lifecycle_auth_and_conflict_errors(tmp_path):
    client, resources = build_client(tmp_path)
    alert = resources.execution_alert_store.record("CRITICAL", ("BROKER_FAILURE",), "CRITICAL:BROKER_FAILURE")

    assert client.post(f"/execution/alerts/{alert.alert_id}/acknowledge").status_code == 401
    headers = {"X-Execution-Health-Token": "test-token"}
    client.post(f"/execution/alerts/{alert.alert_id}/resolve", headers=headers)
    assert client.post(f"/execution/alerts/{alert.alert_id}/acknowledge", headers=headers).status_code == 409
    assert client.post("/execution/alerts/999999/resolve", headers=headers).status_code == 404
