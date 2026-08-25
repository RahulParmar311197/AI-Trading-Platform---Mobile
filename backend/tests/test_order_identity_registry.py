from app.order_identity_registry import OrderIdentity, OrderIdentityRegistry


def test_identity_survives_restart_and_prevents_conflicting_binding(tmp_path):
    path = str(tmp_path / "identity.db")
    registry = OrderIdentityRegistry(path)
    identity = OrderIdentity("client-1", "upstox", "broker-123")
    registry.bind(identity)
    assert registry.by_client("client-1") == identity
    assert registry.by_broker("upstox", "broker-123") == identity
    try:
        registry.bind(OrderIdentity("client-1", "upstox", "broker-999"))
    except ValueError:
        pass
    else:
        raise AssertionError("conflicting binding should fail")
    registry.close()
    reopened = OrderIdentityRegistry(path)
    assert reopened.by_broker("upstox", "broker-123") == identity
    reopened.close()
