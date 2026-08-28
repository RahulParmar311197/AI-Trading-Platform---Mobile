from pathlib import Path


def test_main_uses_canonical_broker_context_attestor():
    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")

    assert "execution_broker_router = build_broker_router(" in source
    assert "context_attestor=resources.broker_context_attestor" in source


def test_main_provisions_and_validates_active_account_routes_before_recovery():
    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")

    provision_marker = "provisioning_errors = provision_active_account_routes(db, execution_broker_router)"
    validate_marker = "route_validation_errors = validate_active_account_routes(db, execution_broker_router)"
    recovery_marker = "result = broker_recovery.run(lifecycle, route=recovery_route)"

    assert provision_marker in source
    assert validate_marker in source
    assert source.index(provision_marker) < source.index(recovery_marker)
    assert source.index(validate_marker) < source.index(recovery_marker)


def test_main_does_not_use_default_route_for_multiple_active_accounts():
    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")

    assert "if len(active_accounts) > 1:" in source
    assert "MULTI_ACCOUNT_RECONCILIATION_REQUIRED" in source
    assert "startup recovery supports one active broker account" in source


def test_main_passes_account_bound_route_to_recovery_and_positions():
    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")

    assert "recovery_route = account_route_name(active_accounts[0]) if active_accounts else None" in source
    assert "broker_recovery.run(lifecycle, route=recovery_route)" in source
    assert "execution_broker_router.get_positions(recovery_route)" in source
