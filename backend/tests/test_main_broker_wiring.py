from pathlib import Path


def test_main_uses_canonical_broker_context_attestor():
    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")

    assert "execution_broker_router = build_broker_router(" in source
    assert "context_attestor=resources.broker_context_attestor" in source


def test_main_provisions_and_validates_active_account_routes_before_recovery():
    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")

    provision_marker = "provisioning_errors = provision_active_account_routes(db, execution_broker_router)"
    validate_marker = "route_validation_errors = validate_active_account_routes(db, execution_broker_router)"
    recovery_marker = "result = broker_recovery.run(lifecycle)"

    assert provision_marker in source
    assert validate_marker in source
    assert source.index(provision_marker) < source.index(recovery_marker)
    assert source.index(validate_marker) < source.index(recovery_marker)
