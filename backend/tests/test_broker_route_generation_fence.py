from datetime import datetime, timezone

import pytest

from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.broker_factory import account_route_generation, build_account_route
from app.broker_router import BrokerRoute, BrokerRouter
from app.models.broker_account import BrokerAccount
from app.safety_state import SafetyStateStore


def _account(account_id: int, updated_at: datetime) -> BrokerAccount:
    return BrokerAccount(
        id=account_id,
        user_id=1,
        broker="upstox",
        account_label=f"account-{account_id}",
        encrypted_credentials="unused",
        status="active",
        updated_at=updated_at,
    )


def test_account_route_generation_changes_when_account_version_changes():
    first = _account(42, datetime(2026, 8, 26, 3, 0, tzinfo=timezone.utc))
    second = _account(42, datetime(2026, 8, 26, 3, 1, tzinfo=timezone.utc))
    assert account_route_generation(first) != account_route_generation(second)


def test_router_rejects_stale_account_route_generation(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    router = BrokerRouter(
        [BrokerRoute("upstox:account:42", PaperBrokerAdapter(), broker_account_id=42, generation="generation-2")],
        "upstox:account:42",
        safety_store=store,
    )
    request = BrokerOrderRequest(
        client_order_id="client-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        broker_route="upstox:account:42",
        broker_account_id=42,
        broker_route_generation="generation-1",
    )

    with pytest.raises(RuntimeError, match="route generation is stale"):
        router.submit(request)


def test_router_requires_generation_for_account_bound_submission(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    router = BrokerRouter(
        [BrokerRoute("upstox:account:42", PaperBrokerAdapter(), broker_account_id=42, generation="generation-1")],
        "upstox:account:42",
        safety_store=store,
    )
    request = BrokerOrderRequest(
        client_order_id="client-2",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        broker_route="upstox:account:42",
        broker_account_id=42,
    )

    with pytest.raises(RuntimeError, match="route generation is required"):
        router.submit(request)
