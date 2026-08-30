from app.app_factory import create_resources


class DecisionEngine:
    pass


class InstrumentProvider:
    pass


class Submitter:
    pass


def test_server_database_resources_expose_durable_risk_reservation_store(tmp_path):
    resources = create_resources(
        database_url=f"sqlite:///{tmp_path / 'risk.db'}",
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.sqlite3"),
        safety_path=str(tmp_path / "safety.json"),
        audit_path=str(tmp_path / "audit.jsonl"),
        alert_path=str(tmp_path / "alerts.sqlite3"),
        alert_event_path=str(tmp_path / "events.sqlite3"),
        execution_authorization_path=str(tmp_path / "authorization.sqlite3"),
        submission_intent_path=str(tmp_path / "submission_intents.json"),
    )

    assert resources.risk_reservation_store is not None
    assert resources.create_ai_execution_orchestrator(
        decision_engine=DecisionEngine(),
        instrument_provider=InstrumentProvider(),
        order_submitter=Submitter(),
    ).risk_reservation_store is resources.risk_reservation_store


def test_local_resources_block_ai_orchestrator_without_durable_reservation_store(tmp_path):
    resources = create_resources(
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.sqlite3"),
        safety_path=str(tmp_path / "safety.json"),
        audit_path=str(tmp_path / "audit.jsonl"),
        alert_path=str(tmp_path / "alerts.sqlite3"),
        alert_event_path=str(tmp_path / "events.sqlite3"),
        execution_authorization_path=str(tmp_path / "authorization.sqlite3"),
        submission_intent_path=str(tmp_path / "submission_intents.json"),
    )

    assert resources.risk_reservation_store is None
    try:
        resources.create_ai_execution_orchestrator(
            decision_engine=DecisionEngine(),
            instrument_provider=InstrumentProvider(),
            order_submitter=Submitter(),
        )
    except RuntimeError as exc:
        assert "durable risk reservation store" in str(exc)
    else:
        raise AssertionError("AI execution must fail closed without durable risk reservations")
