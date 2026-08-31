from app.app_factory import create_app, create_resources


def test_application_broker_router_uses_canonical_durable_reconciliation_stores(tmp_path):
    resources = create_resources(
        database_url=f"sqlite:///{tmp_path / 'trading.db'}",
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.sqlite3"),
        safety_path=str(tmp_path / "safety.json"),
        audit_path=str(tmp_path / "audit.jsonl"),
        alert_path=str(tmp_path / "alerts.sqlite3"),
        alert_event_path=str(tmp_path / "events.sqlite3"),
        execution_authorization_path=str(tmp_path / "authorization.sqlite3"),
        submission_intent_path=str(tmp_path / "submission_intents.json"),
    )

    app = create_app(resources=resources)
    router = app.state.broker_router

    assert router.submission_intent_store is resources.submission_intent_store
    assert router.reconciliation_engine.submission_intent_store is resources.submission_intent_store
    assert router.reconciliation_engine.state_store is resources.safety_store
    assert router.reconciliation_engine.risk_reservation_store is resources.risk_reservation_store


def test_application_broker_router_without_database_has_no_durable_reservation_capability(tmp_path):
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

    app = create_app(resources=resources)
    assert resources.risk_reservation_store is None
    assert app.state.broker_router.reconciliation_engine.risk_reservation_store is None
