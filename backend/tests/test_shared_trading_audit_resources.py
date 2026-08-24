from app.app_factory import create_resources


def test_resources_share_single_audit_log(tmp_path):
    resources = create_resources(
        execution_path=str(tmp_path / 'execution.json'),
        idempotency_path=str(tmp_path / 'idempotency.sqlite3'),
        safety_path=str(tmp_path / 'safety.json'),
        audit_path=str(tmp_path / 'audit.jsonl'),
    )
    assert resources.startup_execution_state.audit_log is resources.audit_log
    assert resources.emergency_halt_controller.audit_log is resources.audit_log
