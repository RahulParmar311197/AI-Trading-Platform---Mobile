from types import SimpleNamespace
from unittest.mock import Mock

from app.broker_recovery import BrokerStartupRecovery
from app.reconciliation_result import ReconciliationResult


def test_bound_route_passes_verified_reconciliation_to_recovery_manager():
    route = SimpleNamespace(name="upstox:account:7", broker_account_id=7, generation="gen-1")
    verified = Mock(spec=ReconciliationResult)
    verified.context = object()

    router = SimpleNamespace(
        context_attestor=object(),
        reconciliation_engine=object(),
        get=Mock(return_value=route),
        get_snapshot=Mock(return_value=object()),
    )
    manager = Mock()
    manager.startup.return_value = SimpleNamespace(ready=True)
    execution_store = Mock()
    lifecycle = SimpleNamespace(orders={}, positions={})

    recovery = BrokerStartupRecovery(router, execution_store, Mock(), manager)
    recovery.manager = manager

    # Replace the coordinator construction boundary so this unit test focuses on
    # the recovery contract rather than cryptographic attestation internals.
    import app.broker_recovery as module
    original = module.ReconciliationCoordinator
    coordinator = Mock()
    coordinator.return_value.reconcile.return_value = verified
    module.ReconciliationCoordinator = coordinator
    try:
        result = recovery.run(lifecycle, route=route.name)
    finally:
        module.ReconciliationCoordinator = original

    assert result.ready is True
    execution_store.load.assert_called_once_with(lifecycle)
    manager.startup.assert_called_once()
    kwargs = manager.startup.call_args.kwargs
    assert kwargs["verified_reconciliation"] is verified
    assert kwargs["active_context"] is verified.context
    coordinator.return_value.reconcile.assert_called_once()


def test_unbound_route_keeps_recovery_manager_fallback():
    route = SimpleNamespace(name="paper", broker_account_id=None, generation=None)
    router = SimpleNamespace(
        context_attestor=object(),
        reconciliation_engine=object(),
        get=Mock(return_value=route),
        get_snapshot=Mock(return_value=object()),
    )
    manager = Mock()
    manager.startup.return_value = SimpleNamespace(ready=False)
    execution_store = Mock()
    lifecycle = SimpleNamespace(orders={}, positions={})

    recovery = BrokerStartupRecovery(router, execution_store, Mock(), manager)
    result = recovery.run(lifecycle, route=route.name)

    assert result.ready is False
    execution_store.load.assert_not_called()
    manager.startup.assert_called_once()
    assert "verified_reconciliation" not in manager.startup.call_args.kwargs
