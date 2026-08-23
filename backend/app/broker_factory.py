from __future__ import annotations

import os

from app.broker_adapter import PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.dhan_adapter import DhanAdapter


def build_broker_router() -> BrokerRouter:
    """Create the configured broker router without making network calls."""
    selected = os.getenv("BROKER_ROUTE", "paper").strip().lower()
    routes = [BrokerRoute("paper", PaperBrokerAdapter())]

    dhan = DhanAdapter()
    routes.append(BrokerRoute("dhan", dhan, enabled=bool(dhan.config.live_enabled)))

    return BrokerRouter(routes, selected)
