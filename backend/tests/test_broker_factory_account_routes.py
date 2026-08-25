from types import SimpleNamespace

from app.broker_factory import account_route_name, validate_active_account_routes
from app.broker_router import BrokerRoute, BrokerRouter


class FakeQuery:
    def __init__(self, accounts):
        self.accounts = accounts

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.accounts)


class FakeDB:
    def __init__(self, accounts):
        self.accounts = accounts

    def query(self, _model):
        return FakeQuery(self.accounts)


class FakeAdapter:
    pass


def test_account_route_name_is_canonical():
    account = SimpleNamespace(id=42, broker="Upstox")
    assert account_route_name(account) == "upstox:account:42"


def test_active_account_without_bound_route_fails_closed():
    account = SimpleNamespace(id=42, broker="upstox", status="active")
    router = BrokerRouter([BrokerRoute("paper", FakeAdapter())], "paper")

    errors = validate_active_account_routes(FakeDB([account]), router)

    assert errors == ["account:42:upstox:account:42:route_not_registered"]


def test_bound_account_route_must_match_account_identity():
    account = SimpleNamespace(id=42, broker="upstox", status="active")
    router = BrokerRouter(
        [
            BrokerRoute("paper", FakeAdapter()),
            BrokerRoute("upstox:account:42", FakeAdapter(), broker_account_id=7),
        ],
        "paper",
    )

    errors = validate_active_account_routes(FakeDB([account]), router)

    assert errors == ["account:42:upstox:account:42:route_account_mismatch"]


def test_bound_account_route_is_ready():
    account = SimpleNamespace(id=42, broker="upstox", status="active")
    router = BrokerRouter(
        [
            BrokerRoute("paper", FakeAdapter()),
            BrokerRoute("upstox:account:42", FakeAdapter(), broker_account_id=42),
        ],
        "paper",
    )

    assert validate_active_account_routes(FakeDB([account]), router) == []
