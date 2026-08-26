import json
from types import SimpleNamespace

from cryptography.fernet import Fernet

from app.api.broker_accounts import BrokerAccountUpdate, update_account
from app.broker_adapter import PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.security.credential_encryption import encrypt_credentials


def _request(router):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(broker_router=router)))


def _account(monkeypatch, account_id=42, token="old-token", status="active"):
    monkeypatch.setenv("BROKER_CREDENTIALS_KEY", Fernet.generate_key().decode())
    return BrokerAccount(
        id=account_id,
        user_id=7,
        broker="upstox",
        account_label=f"upstox-{account_id}",
        encrypted_credentials=encrypt_credentials(json.dumps({"access_token": token})),
        status=status,
    )


def _user():
    return User(id=7, email="owner@example.com", password_hash="hash")


def test_credential_update_replaces_live_account_route(monkeypatch, test_session_factory):
    account = _account(monkeypatch)
    with test_session_factory() as db:
        db.add(account)
        db.commit()
        router = BrokerRouter([BrokerRoute("paper", PaperBrokerAdapter())], "paper")
        router.routes["upstox:account:42"] = BrokerRoute(
            "upstox:account:42", PaperBrokerAdapter(), broker_account_id=42
        )

        result = update_account(
            42,
            BrokerAccountUpdate(credentials='{"access_token":"new-token"}'),
            _request(router),
            db,
            _user(),
        )

        assert result["status"] == "active"
        assert router.routes["upstox:account:42"].broker_account_id == 42
        assert router.routes["upstox:account:42"].adapter.config.access_token == "new-token"


def test_disabling_account_removes_live_route(monkeypatch, test_session_factory):
    account = _account(monkeypatch)
    with test_session_factory() as db:
        db.add(account)
        db.commit()
        router = BrokerRouter([BrokerRoute("paper", PaperBrokerAdapter())], "paper")
        router.routes["upstox:account:42"] = BrokerRoute(
            "upstox:account:42", PaperBrokerAdapter(), broker_account_id=42
        )

        result = update_account(
            42,
            BrokerAccountUpdate(status="disabled"),
            _request(router),
            db,
            _user(),
        )

        assert result["status"] == "disabled"
        assert "upstox:account:42" not in router.routes


def test_failed_credential_rotation_disables_account_and_removes_route(monkeypatch, test_session_factory):
    account = _account(monkeypatch)
    with test_session_factory() as db:
        db.add(account)
        db.commit()
        router = BrokerRouter([BrokerRoute("paper", PaperBrokerAdapter())], "paper")
        router.routes["upstox:account:42"] = BrokerRoute(
            "upstox:account:42", PaperBrokerAdapter(), broker_account_id=42
        )

        result_error = None
        try:
            update_account(
                42,
                BrokerAccountUpdate(credentials="not-json-credentials"),
                _request(router),
                db,
                _user(),
            )
        except Exception as exc:
            result_error = exc

        db.refresh(account)
        assert result_error is not None
        assert account.status == "disabled"
        assert "upstox:account:42" not in router.routes
