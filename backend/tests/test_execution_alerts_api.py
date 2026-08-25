from fastapi.testclient import TestClient

from app.app_factory import create_app, create_resources


def test_execution_alerts_endpoint_returns_persisted_history(tmp_path):
    resources = create_resources(
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.db"),
        safety_path=str(tmp_path / "safety.json"),
        audit_path=str(tmp_path / "audit.jsonl"),
        alert_path=str(tmp_path / "alerts.db"),
    )
    resources.execution_alert_store.record("CRITICAL", ("BROKER_FAILURE",), "CRITICAL:BROKER_FAILURE")
    client = TestClient(create_app(resources=resources))

    assert client.get("/execution/alerts").status_code == 401
    response = client.get("/execution/alerts", headers={"X-Execution-Health-Token": "test-token"})
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["severity"] == "CRITICAL"
    assert payload[0]["reason_codes"] == ["BROKER_FAILURE"]
