from __future__ import annotations

from collections.abc import Callable, Iterable

from app.broker_adapter import BrokerAdapter
from app.broker_router import BrokerRoute


SUPPORTED_BROKERS = {"dhan", "upstox", "paper"}


def build_account_routes(
    accounts: Iterable[object],
    adapter_factory: Callable[[object], BrokerAdapter],
) -> list[BrokerRoute]:
    """Build one broker route per active persisted BrokerAccount.

    The factory intentionally requires an adapter factory so credential decryption and
    broker-specific configuration stay outside this module. It never falls back to a
    global adapter when an account is missing or inactive.
    """
    routes: list[BrokerRoute] = []
    seen: set[int] = set()
    for account in accounts:
        account_id = getattr(account, "id", None)
        broker = str(getattr(account, "broker", "")).strip().lower()
        status = str(getattr(account, "status", "")).strip().lower()
        if account_id is None or int(account_id) <= 0:
            raise ValueError("broker account id must be positive")
        account_id = int(account_id)
        if account_id in seen:
            raise ValueError(f"duplicate broker account id: {account_id}")
        if status != "active":
            continue
        if broker not in SUPPORTED_BROKERS:
            raise ValueError(f"unsupported broker: {broker}")

        adapter = adapter_factory(account)
        if not isinstance(adapter, BrokerAdapter):
            raise TypeError("adapter_factory must return a BrokerAdapter")

        route_name = f"{broker}:account:{account_id}"
        routes.append(BrokerRoute(route_name, adapter, enabled=True, broker_account_id=account_id))
        seen.add(account_id)
    return routes
