from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.broker_accounts as broker_accounts


class DB:
    def __init__(self, fail_commit=False):
        self.fail_commit = fail_commit
        self.commits = 0
        self.rolled_back = False
        self.refreshed = None

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("db unavailable")

    def rollback(self):
        self.rolled_back = True

    def refresh(self, row):
        self.refreshed = row


class LockRouter:
    def __init__(self, safety_store=None):
        self.routes = {}
        self.safety_store = safety_store

    def route_lifecycle_lock(self):
        from contextlib import nullcontext
        return nullcontext()


class SafetyStore:
    def __init__(self):
        self.halted = []

    def halt(self, reason):
        self.halted.append(reason)


def request_for(router):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(broker_router=router)))


def account():
    return SimpleNamespace(
        id=12,
        broker="paper",
        account_label="primary",
        encrypted_credentials="encrypted",
        status="active",
        updated_at="2026-08-28T08:00:00+00:00",
    )


def test_route_validation_failure_disables_account_and_removes_route(monkeypatch):
    row = account()
    router = LockRouter()
    router.routes["paper:account:12"] = SimpleNamespace(broker_account_id=12, enabled=True)
    db = DB()
    monkeypatch.setattr(broker_accounts, "account_route_name", lambda account: "paper:account:12")

    with pytest.raises(HTTPException) as exc:
        broker_accounts._quarantine_account_after_route_validation_failure(
            request_for(router), db, row, ["account:12:route_generation_stale"]
        )

    assert exc.value.status_code == 503
    assert row.status == "disabled"
    assert "paper:account:12" not in router.routes
    assert db.commits == 1
    assert db.refreshed is row
    assert exc.value.detail["errors"] == ["account:12:route_generation_stale"]


def test_route_validation_failure_quarantine_db_error_halts_trading(monkeypatch):
    row = account()
    safety = SafetyStore()
    router = LockRouter(safety)
    router.routes["paper:account:12"] = SimpleNamespace(broker_account_id=12, enabled=True)
    db = DB(fail_commit=True)
    monkeypatch.setattr(broker_accounts, "account_route_name", lambda account: "paper:account:12")

    with pytest.raises(HTTPException) as exc:
        broker_accounts._quarantine_account_after_route_validation_failure(
            request_for(router), db, row, ["account:12:route_not_registered"]
        )

    assert exc.value.status_code == 500
    assert db.rolled_back is True
    assert safety.halted
    assert "trading halted" in exc.value.detail
