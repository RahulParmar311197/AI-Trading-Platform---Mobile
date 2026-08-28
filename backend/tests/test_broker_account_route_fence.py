from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.broker_accounts import _delete_account_with_route_fence
from app.models.broker_account import BrokerAccount


def account():
    return BrokerAccount(id=7, user_id=1, broker="upstox", account_label="primary", status="disabled")


class DB:
    def __init__(self, fail_commit=False):
        self.fail_commit = fail_commit
        self.deleted = None
        self.rolled_back = False
        self.commits = 0

    def delete(self, row):
        self.deleted = row

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("db unavailable")

    def rollback(self):
        self.rolled_back = True


class Router:
    def __init__(self, route):
        self.routes = {route.name: route}
        self.safety_store = None

    def route_lifecycle_lock(self):
        from contextlib import nullcontext
        return nullcontext()


class Request:
    def __init__(self, router):
        self.app = SimpleNamespace(state=SimpleNamespace(broker_router=router))


def route(account_id=7, enabled=True):
    return SimpleNamespace(name="upstox:account:7", broker_account_id=account_id, enabled=enabled)


def test_route_is_removed_before_successful_db_delete():
    row = account()
    router = Router(route())
    _delete_account_with_route_fence(Request(router), DB(), row)
    assert "upstox:account:7" not in router.routes


def test_db_failure_restores_route_and_rolls_back():
    row = account()
    router = Router(route())
    db = DB(fail_commit=True)
    with pytest.raises(HTTPException) as exc:
        _delete_account_with_route_fence(Request(router), db, row)
    assert exc.value.status_code == 500
    assert "upstox:account:7" in router.routes
    assert db.rolled_back is True


def test_missing_route_fails_closed_before_db_mutation():
    row = account()
    router = Router(route())
    router.routes.clear()
    db = DB()
    with pytest.raises(HTTPException) as exc:
        _delete_account_with_route_fence(Request(router), db, row)
    assert exc.value.status_code == 503
    assert db.deleted is None
    assert db.commits == 0


def test_route_identity_mismatch_fails_closed():
    row = account()
    router = Router(route(account_id=99))
    db = DB()
    with pytest.raises(HTTPException) as exc:
        _delete_account_with_route_fence(Request(router), db, row)
    assert exc.value.status_code == 503
    assert db.deleted is None
    assert db.commits == 0


def test_disabled_route_fails_closed():
    row = account()
    router = Router(route(enabled=False))
    db = DB()
    with pytest.raises(HTTPException) as exc:
        _delete_account_with_route_fence(Request(router), db, row)
    assert exc.value.status_code == 503
    assert db.deleted is None
    assert db.commits == 0
