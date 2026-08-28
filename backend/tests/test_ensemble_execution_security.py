from types import SimpleNamespace

import pytest

from app.api import ensemble


class _FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.expunge_calls = []

    def query(self, model):
        return _FakeQuery(self.rows)

    def expunge(self, account):
        self.expunge_calls.append(account)


class _FakeSessionContext:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc, tb):
        return False


def _account(account_id=7):
    return SimpleNamespace(id=account_id, user_id=42, broker="paper", status="active", updated_at=None)


def test_ai_execute_rejects_authenticated_user_mismatch_before_execution(monkeypatch):
    class Request:
        class State:
            resources = None

        app = SimpleNamespace(state=State())

    monkeypatch.setattr(ensemble, "require_trading_ready", lambda request: None)
    payload = ensemble.DecisionExecuteRequest(
        user_id=99,
        symbol="NIFTY",
        quantity=1,
        client_order_id="AI-1",
    )

    with pytest.raises(ensemble.HTTPException) as exc:
        ensemble.execute(Request(), payload, SimpleNamespace(id=42))

    assert exc.value.status_code == 403
    assert exc.value.detail == "USER_IDENTITY_MISMATCH"


def test_ai_account_resolution_rejects_ambiguous_accounts(monkeypatch):
    accounts = [_account(7), _account(8)]
    monkeypatch.setattr(ensemble, "SessionLocal", lambda: _FakeSessionContext(_FakeDb(accounts)))

    with pytest.raises(ensemble.HTTPException) as exc:
        ensemble._resolve_broker_account(42, None)

    assert exc.value.status_code == 409
    assert exc.value.detail == "BROKER_ACCOUNT_SELECTION_REQUIRED"


def test_ai_account_resolution_rejects_account_owned_by_another_user(monkeypatch):
    monkeypatch.setattr(ensemble, "SessionLocal", lambda: _FakeSessionContext(_FakeDb([])))

    with pytest.raises(ensemble.HTTPException) as exc:
        ensemble._resolve_broker_account(42, 7)

    assert exc.value.status_code == 403
    assert exc.value.detail == "BROKER_ACCOUNT_NOT_OWNED_OR_ACTIVE"


def test_ai_execution_service_requires_canonical_startup_state(monkeypatch):
    captured = {}

    class FakeService:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    class FakeRecovery:
        pass

    class FakeProvider:
        def __init__(self, *args):
            pass

    class FakeGate:
        def __init__(self, *args):
            pass

    monkeypatch.setattr(ensemble, "PreTradeRiskGate", FakeGate)
    monkeypatch.setattr(ensemble, "RuntimeRiskSnapshotProvider", FakeProvider)
    monkeypatch.setattr(ensemble, "ExecutionAuthorization", lambda *args, **kwargs: object())

    import app.order_execution_service as execution_module
    import app.startup_recovery as recovery_module

    monkeypatch.setattr(execution_module, "OrderExecutionService", FakeService)
    monkeypatch.setattr(recovery_module, "StartupRecoveryCoordinator", FakeRecovery)

    resources = SimpleNamespace(
        audit_log=object(),
        execution_store=SimpleNamespace(load=lambda lifecycle: None),
        idempotency_store=object(),
        authorization=object(),
        safety_store=object(),
        startup_execution_state=object(),
        execution_observability=object(),
        connectivity_registry=object(),
    )

    ensemble._execution_service(object(), resources)

    assert captured["startup_state"] is resources.startup_execution_state
    assert captured["connectivity_registry"] is resources.connectivity_registry
    assert captured["audit_log"] is resources.audit_log
    assert captured["observability"] is resources.execution_observability
