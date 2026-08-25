from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.broker_adapter import PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.dhan_adapter import DhanAdapter
from app.models import BrokerAccount
from app.safety_state import SafetyStateStore
from app.upstox_adapter import UpstoxAdapter


def build_broker_router(safety_store: SafetyStateStore | None = None) -> BrokerRouter:
    """Create the configured broker router without making network calls."""
    selected = os.getenv("BROKER_ROUTE", "paper").strip().lower()
    routes = [BrokerRoute("paper", PaperBrokerAdapter())]

    dhan = DhanAdapter()
    routes.append(BrokerRoute("dhan", dhan, enabled=bool(dhan.config.live_enabled)))

    upstox = UpstoxAdapter()
    routes.append(BrokerRoute("upstox", upstox, enabled=bool(upstox.config.live_enabled)))

    return BrokerRouter(routes, selected, safety_store=safety_store or SafetyStateStore())


def account_route_name(account: BrokerAccount) -> str:
    """Return the canonical route name for a persisted broker account."""
    broker = str(account.broker or "").strip().lower()
    if not broker or account.id is None or int(account.id) <= 0:
        raise ValueError("broker account has invalid route identity")
    return f"{broker}:account:{int(account.id)}"


def validate_active_account_routes(db: Session, router: BrokerRouter) -> list[str]:
    """Return fail-closed route-binding errors for every active broker account."""
    errors: list[str] = []
    accounts = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.status == "active")
        .order_by(BrokerAccount.id.asc())
        .all()
    )
    for account in accounts:
        try:
            route_name = account_route_name(account)
        except ValueError as exc:
            errors.append(f"account:{account.id}:invalid_identity:{exc}")
            continue
        route = router.routes.get(route_name)
        if route is None:
            errors.append(f"account:{account.id}:{route_name}:route_not_registered")
            continue
        if not route.enabled:
            errors.append(f"account:{account.id}:{route_name}:route_disabled")
            continue
        if route.broker_account_id != int(account.id):
            errors.append(f"account:{account.id}:{route_name}:route_account_mismatch")
    return errors
