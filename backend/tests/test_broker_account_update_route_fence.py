from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.broker_accounts import _update_account_with_route_fence
from app.models.broker_account import BrokerAccount


class DB:
    def __init__(self, fail_commit=False):
        self.fail_commit = fail_commit
        self.commits = 0
        self.rolled_back = False

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("db unavailable")

    def rollback(self):
        self.rolled_back = True

    def refresh(self, _row):
        return None


class Router:
    def __init__(self, route=None):
        self.routes = {} if route is None else {route.name: route}

    def route_lifecycle_lock(self):
        from contextlib import nullcontext
        return nullcontext()


class Request:
    def __init__(self, router):
        self.app = SimpleNamespace(state=SimpleNamespace(broker_router=router))


def account():
    return BrokerAccount(
        id=7,
        user_id=1,
        broker="paper",
        account_label="primary",
        encrypted_credentials="old",
        status="active",
    )


def route(account_id=7, generation=None):
    return SimpleNamespace(
        name="paper:account:7",
        broker_account_id=account_id,
        generation=generation,
        enabled=True,
    )


def test_invalid_candidate_leaves_old_credentials_and_route(monkeypatch):
    row = account()
    old_route = route(generation=None)
    router = Router(old_route)
    monkeypatch.setattr(
        "app.api.broker_accounts.encrypt_credentials",
        lambda value: f"encrypted:{value}",
    )
    monkeypatch.setattr(
        "app.api.broker_accounts.build_account_route",
        lambda _account: (_ for _ in ()).throw(ValueError("bad credentials")),
    )

    with pytest.raises(HTTPException) as exc:
        _update_account_with_route_fence(Request(router), DB(), row, credentials="new", status="active")

    assert exc.value.status_code == 409
    assert row.encrypted_credentials == "old"
    assert row.status == "active"
    assert router.routes[old_route.name] is old_route


def test_db_failure_restores_old_credentials_and_route(monkeypatch):
    row = account()
    old_route = route(generation=None)
    router = Router(old_route)
    candidate = route(generation=None)
    monkeypatch.setattr(
        "app.api.broker_accounts.encrypt_credentials",
        lambda value: f"encrypted:{value}",
    )
    monkeypatch.setattr("app.api.broker_accounts.build_account_route", lambda _account: candidate)
    db = DB(fail_commit=True)

    with pytest.raises(HTTPException) as exc:
        _update_account_with_route_fence(Request(router), db, row, credentials="new", status="active")

    assert exc.value.status_code == 409
    assert db.rolled_back is True
    assert row.encrypted_credentials == "old"
    assert row.status == "active"
    assert router.routes[old_route.name] is old_route


def test_successful_rotation_publishes_candidate_before_commit(monkeypatch):
    row = account()
    router = Router(route())
    candidate = route(generation=None)
    monkeypatch.setattr(
        "app.api.broker_accounts.encrypt_credentials",
        lambda value: f"encrypted:{value}",
    )

    observed = {}

    def build(_account):
        observed["route_at_build"] = router.routes.get("paper:account:7")
        return candidate

    monkeypatch.setattr("app.api.broker_accounts.build_account_route", build)

    class ObservingDB(DB):
        def commit(self):
            observed["route_at_commit"] = router.routes.get("paper:account:7")
            super().commit()

    _update_account_with_route_fence(Request(router), ObservingDB(), row, credentials="new", status="active")

    assert observed["route_at_build"] is not None
    assert observed["route_at_commit"] is candidate
    assert router.routes["paper:account:7"] is candidate
    assert row.encrypted_credentials == "encrypted:new"


def test_disabling_account_removes_route_and_commit_failure_restores_it():
    row = account()
    old_route = route()
    router = Router(old_route)
    db = DB(fail_commit=True)

    with pytest.raises(HTTPException) as exc:
        _update_account_with_route_fence(Request(router), db, row, credentials=None, status="disabled")

    assert exc.value.status_code == 409
    assert row.status == "active"
    assert router.routes[old_route.name] is old_route
    assert db.rolled_back is True
