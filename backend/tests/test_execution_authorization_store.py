from datetime import datetime, timedelta, timezone

from app.execution_authorization_store import ExecutionAuthorizationStore
from app.live_execution_gateway import ExecutionAuthorization


def authorization(*, expires_at=None):
    return ExecutionAuthorization(
        _nonce="test-nonce",
        _order_fingerprint="order-fingerprint",
        _expires_at=expires_at or datetime.now(timezone.utc) + timedelta(seconds=30),
    )


def test_authorization_survives_independent_store_instances(tmp_path):
    path = str(tmp_path / "execution-authorizations.sqlite3")
    first = ExecutionAuthorizationStore(path)
    token = authorization()
    first.issue(token)
    first.close()

    second = ExecutionAuthorizationStore(path)
    assert second.consume(token, token._order_fingerprint, lambda: datetime.now(timezone.utc)) == "consumed_now"
    second.close()


def test_authorization_cannot_be_consumed_twice_across_store_instances(tmp_path):
    path = str(tmp_path / "execution-authorizations.sqlite3")
    first = ExecutionAuthorizationStore(path)
    second = ExecutionAuthorizationStore(path)
    token = authorization()
    first.issue(token)

    assert first.consume(token, token._order_fingerprint, lambda: datetime.now(timezone.utc)) == "consumed_now"
    assert second.consume(token, token._order_fingerprint, lambda: datetime.now(timezone.utc)) == "consumed"
    first.close()
    second.close()


def test_authorization_rejects_order_mismatch_without_consuming(tmp_path):
    path = str(tmp_path / "execution-authorizations.sqlite3")
    store = ExecutionAuthorizationStore(path)
    token = authorization()
    store.issue(token)

    assert store.consume(token, "different-order", lambda: datetime.now(timezone.utc)) == "order_mismatch"
    assert store.consume(token, token._order_fingerprint, lambda: datetime.now(timezone.utc)) == "consumed_now"
    store.close()


def test_expired_authorization_remains_unconsumed(tmp_path):
    path = str(tmp_path / "execution-authorizations.sqlite3")
    store = ExecutionAuthorizationStore(path)
    now = datetime.now(timezone.utc)
    token = authorization(expires_at=now - timedelta(seconds=1))
    store.issue(token)

    assert store.consume(token, token._order_fingerprint, lambda: now) == "expired"
    store.close()
