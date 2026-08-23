from __future__ import annotations

import os

from app.broker_adapter import PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.dhan_adapter import DhanAdapter
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
