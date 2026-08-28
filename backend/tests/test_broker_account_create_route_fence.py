from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.broker_accounts as broker_accounts


class DB:
    def __init__(self, fail_commit=False):
        self.fail_commit = fail_commit
        self.added = None
        self.flushed = False
        self.commits = 0
        self.rolled_back = False
        self.refreshed = None

    def add(self, row):
        self.added = row

    def flush(self):
        self.flushed = True
        self.added.id = 12
        self.added.updated_at = "2026-08-28T08:00:00+00:00"

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("db unavailable")

    def rollback(self):
        self.rolled_back = True

    def refresh(self, row):
        self.refreshed = row


class Router:
    def __init__(self):
        self.routes = {}

    def route_lifecycle_lock(self):
        from contextlib import nullcontext
        return nullcontext()


class Request:
    def __init__(self, router):
        self.app = SimpleNamespace(state=SimpleNamespace(broker_router=router))


def account():
    return SimpleNamespace(
        id=None,
        user_id=1,
        broker="paper",
        account_label="primary",
        encrypted_credentials="encrypted",
        status="active",
        updated_at=None,
    )


def candidate_route():
    return SimpleNamespace(
        name="paper:account:12",
        broker_account_id=12,
        generation="account:12:2026-08-28T08:00:00+00:00",
        enabled=True,
    )


def test_create_publishes_route_before_successful_commit(monkeypatch):
    row = account()
    router = Router()
    db = DB()
    monkeypatch.setattr(broker_accounts, "build_account_route", lambda account: candidate_route())

    broker_accounts._create_account_with_route_fence(Request(router), db, row)

    assert db.flushed is True
    assert db.commits == 1
    assert db.refreshed is row
    assert router.routes["paper:account:12"].broker_account_id == 12


def test_create_db_failure_rolls_back_and_removes_candidate_route(monkeypatch):
    row = account()
    router = Router()
    db = DB(fail_commit=True)
    monkeypatch.setattr(broker_accounts, "build_account_route", lambda account: candidate_route())

    with pytest.raises(HTTPException) as exc:
        broker_accounts._create_account_with_route_fence(Request(router), db, row)

    assert exc.value.status_code == 409
    assert db.rolled_back is True
    assert router.routes == {}


def test_create_candidate_failure_rolls_back_without_route(monkeypatch):
    row = account()
    router = Router()
    db = DB()
    monkeypatch.setattr(broker_accounts, "build_account_route", lambda account: (_ for _ in ()).throw(ValueError("bad credentials")))

    with pytest.raises(HTTPException) as exc:
        broker_accounts._create_account_with_route_fence(Request(router), db, row)

    assert exc.value.status_code == 409
    assert db.rolled_back is True
    assert db.commits == 0
    assert router.routes == {}


def test_create_refuses_route_collision_before_commit(monkeypatch):
    row = account()
    router = Router()
    router.routes["paper:account:12"] = candidate_route()
    db = DB()
    monkeypatch.setattr(broker_accounts, "build_account_route", lambda account: candidate_route())

    with pytest.raises(HTTPException) as exc:
        broker_accounts._create_account_with_route_fence(Request(router), db, row)

    assert exc.value.status_code == 409
    assert db.commits == 0
    assert router.routes["paper:account:12"].broker_account_id == 12
