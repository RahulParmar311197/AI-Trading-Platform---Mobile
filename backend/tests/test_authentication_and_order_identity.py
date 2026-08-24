import hashlib
import inspect

from app.api.orders import OrderRequest, create_order
from app.auth.security import create_access_token, decode_access_token, hash_password, needs_password_upgrade, verify_password
from app.config import get_settings


def test_password_hash_is_not_legacy_sha256():
    hashed = hash_password("correct horse battery staple")
    assert hashed != hashlib.sha256(b"correct horse battery staple").hexdigest()
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_legacy_sha256_hash_can_be_verified_and_upgraded():
    legacy = hashlib.sha256(b"correct horse battery staple").hexdigest()
    assert needs_password_upgrade(legacy)
    assert verify_password("correct horse battery staple", legacy)
    upgraded = hash_password("correct horse battery staple")
    assert not needs_password_upgrade(upgraded)
    assert verify_password("correct horse battery staple", upgraded)


def test_access_token_round_trip_preserves_subject(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret", "unit-test-secret")
    token = create_access_token("alice", expires_minutes=5)
    assert decode_access_token(token)["sub"] == "alice"


def test_order_request_user_id_is_optional_because_identity_comes_from_token():
    payload = OrderRequest(symbol="NIFTY", side="BUY", quantity=1)
    assert payload.user_id is None


def test_order_endpoint_requires_authenticated_identity_dependency():
    dependencies = [
        p.default.dependency
        for p in inspect.signature(create_order).parameters.values()
        if hasattr(p.default, "dependency")
    ]
    assert any(getattr(dep, "__name__", "") == "get_current_user" for dep in dependencies)
