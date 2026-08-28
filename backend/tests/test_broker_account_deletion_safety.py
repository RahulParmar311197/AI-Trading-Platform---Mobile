from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.broker_accounts import _ensure_account_safe_to_delete
from app.models.broker_account import BrokerAccount


class Snapshot:
    def __init__(self, rows):
        self.rows = rows

    def require_authoritative(self):
        return self.rows


class Adapter:
    def __init__(self, orders):
        self.orders = orders

    def get_order_snapshot(self):
        return Snapshot(self.orders)


class Router:
    def __init__(self, positions, orders):
        self.positions = positions
        self.route = SimpleNamespace(adapter=Adapter(orders))

    def get_positions(self, route):
        return Snapshot(self.positions)

    def get(self, route):
        return self.route


class App:
    def __init__(self, router):
        self.state = SimpleNamespace(broker_router=router)


class Request:
    def __init__(self, router):
        self.app = App(router)


def account(status="disabled"):
    row = BrokerAccount(id=7, user_id=1, broker="upstox", account_label="primary", status=status)
    return row


def test_deletion_requires_disabled_account():
    with pytest.raises(HTTPException) as exc:
        _ensure_account_safe_to_delete(Request(Router([], [])), account("active"))
    assert exc.value.status_code == 409
    assert "disable" in str(exc.value.detail)


def test_deletion_blocks_open_position():
    with pytest.raises(HTTPException) as exc:
        _ensure_account_safe_to_delete(Request(Router([{"symbol": "NIFTY", "quantity": 1}], [])), account())
    assert exc.value.status_code == 409
    assert "open positions" in str(exc.value.detail)


def test_deletion_blocks_non_terminal_order():
    with pytest.raises(HTTPException) as exc:
        _ensure_account_safe_to_delete(
            Request(Router([], [{"status": "OPEN"}])), account()
        )
    assert exc.value.status_code == 409
    assert "non-terminal orders" in str(exc.value.detail)


def test_deletion_requires_authoritative_order_snapshot():
    class NoSnapshotAdapter:
        pass

    router = SimpleNamespace(
        get_positions=lambda route: Snapshot([]),
        get=lambda route: SimpleNamespace(adapter=NoSnapshotAdapter()),
    )
    with pytest.raises(HTTPException) as exc:
        _ensure_account_safe_to_delete(Request(router), account())
    assert exc.value.status_code == 503
    assert "authoritative broker order snapshot" in str(exc.value.detail)


def test_deletion_allows_disabled_flat_account_with_terminal_orders():
    _ensure_account_safe_to_delete(
        Request(
            Router(
                [{"symbol": "NIFTY", "quantity": 0}],
                [
                    {"status": "FILLED"},
                    {"status": "CANCELED"},
                    {"status": "REJECTED"},
                    {"status": "EXPIRED"},
                ],
            )
        ),
        account(),
    )
