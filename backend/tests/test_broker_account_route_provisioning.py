import json

import pytest
from cryptography.fernet import Fernet

from app.broker_factory import build_account_route
from app.models.broker_account import BrokerAccount
from app.security.credential_encryption import encrypt_credentials


def _configure_key(monkeypatch):
    monkeypatch.setenv("BROKER_CREDENTIALS_KEY", Fernet.generate_key().decode())


def _account(monkeypatch, broker: str, credentials: dict, account_id: int = 42):
    _configure_key(monkeypatch)
    return BrokerAccount(
        id=account_id,
        user_id=7,
        broker=broker,
        account_label=f"{broker}-{account_id}",
        encrypted_credentials=encrypt_credentials(json.dumps(credentials)),
        status="active",
    )


def test_upstox_account_route_uses_only_persisted_credentials(monkeypatch):
    account = _account(monkeypatch, "upstox", {"access_token": "stored-token"})

    route = build_account_route(account)

    assert route.name == "upstox:account:42"
    assert route.broker_account_id == 42
    assert route.enabled is True
    assert route.adapter.config.access_token == "stored-token"
    assert route.adapter.config.live_enabled is True


def test_dhan_account_route_requires_both_credentials(monkeypatch):
    account = _account(monkeypatch, "dhan", {"client_id": "client-only"})

    with pytest.raises(ValueError, match="dhan_credentials_missing"):
        build_account_route(account)


def test_invalid_encrypted_credentials_fail_closed(monkeypatch):
    _configure_key(monkeypatch)
    account = BrokerAccount(
        id=43,
        user_id=7,
        broker="upstox",
        account_label="broken",
        encrypted_credentials="not-valid-ciphertext",
        status="active",
    )

    with pytest.raises(ValueError, match="credentials_unreadable"):
        build_account_route(account)


def test_unsupported_broker_cannot_fall_back_to_global_route(monkeypatch):
    account = _account(monkeypatch, "unknown", {"access_token": "token"}, account_id=44)

    with pytest.raises(ValueError, match="unsupported_broker:unknown"):
        build_account_route(account)
