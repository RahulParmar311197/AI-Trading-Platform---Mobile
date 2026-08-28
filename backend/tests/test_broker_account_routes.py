from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.broker_account_routes import build_account_routes
from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_factory import account_route_generation, account_route_name


class FakeAdapter(BrokerAdapter):
    name = "fake"

    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderUpdate:
        return BrokerOrderUpdate(order_id="1", status="SUBMITTED")

    def cancel_order(self, broker_order_id: str) -> BrokerOrderUpdate:
        return BrokerOrderUpdate(order_id=broker_order_id, status="CANCELLED")

    def get_order(self, broker_order_id: str) -> dict:
        return {"order_id": broker_order_id}

    def get_orders(self) -> list[dict]:
        return []

    def get_positions(self) -> list[dict]:
        return []

    def get_account(self) -> dict:
        return {}


@dataclass
class Account:
    id: int
    broker: str
    status: str = "active"
    updated_at: datetime | None = None


def test_builds_one_route_per_active_account_and_binds_identity():
    accounts = [Account(7, "dhan"), Account(8, "upstox"), Account(9, "dhan", "disabled")]
    routes = build_account_routes(accounts, lambda _: FakeAdapter())

    assert [route.name for route in routes] == ["dhan:account:7", "upstox:account:8"]
    assert [route.broker_account_id for route in routes] == [7, 8]


def test_rejects_duplicate_account_ids():
    with pytest.raises(ValueError, match="duplicate broker account id"):
        build_account_routes([Account(7, "dhan"), Account(7, "upstox")], lambda _: FakeAdapter())


def test_rejects_unsupported_active_broker():
    with pytest.raises(ValueError, match="unsupported broker"):
        build_account_routes([Account(7, "unknown")], lambda _: FakeAdapter())


def test_rejects_adapter_factory_that_is_not_a_broker_adapter():
    with pytest.raises(TypeError, match="BrokerAdapter"):
        build_account_routes([Account(7, "dhan")], lambda _: object())


def test_account_route_name_is_account_scoped():
    account = Account(42, "upstox")
    assert account_route_name(account) == "upstox:account:42"


def test_account_route_generation_is_fenced_by_update_timestamp():
    account = Account(42, "upstox", updated_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc))
    first = account_route_generation(account)
    account.updated_at = datetime(2026, 8, 28, 12, 1, tzinfo=timezone.utc)
    assert first != account_route_generation(account)


def test_invalid_account_identity_is_rejected():
    with pytest.raises(ValueError, match="invalid route identity"):
        account_route_name(Account(0, "upstox"))
