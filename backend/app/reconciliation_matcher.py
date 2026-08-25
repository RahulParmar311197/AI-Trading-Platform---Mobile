from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InternalOrderCandidate:
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    created_at: datetime
    broker_order_id: str | None = None
    broker_account_id: int | None = None
    broker_route: str | None = None


@dataclass(frozen=True)
class BrokerOrderSnapshot:
    broker_order_id: str
    symbol: str
    side: str
    quantity: float
    timestamp: datetime
    client_order_id: str | None = None
    broker_account_id: int | None = None
    broker_route: str | None = None


@dataclass(frozen=True)
class ReconciliationMatch:
    client_order_id: str
    broker_order_id: str
    method: str
    broker_account_id: int | None = None
    broker_route: str | None = None


class ReconciliationMatcher:
    """Fail-closed deterministic matching; account identity is part of the match when supplied."""

    @staticmethod
    def _identity_matches(broker: BrokerOrderSnapshot, candidate: InternalOrderCandidate) -> bool:
        if broker.broker_account_id is not None and candidate.broker_account_id != broker.broker_account_id:
            return False
        if broker.broker_route is not None and candidate.broker_route != broker.broker_route:
            return False
        return True

    @staticmethod
    def match(broker: BrokerOrderSnapshot, candidates: list[InternalOrderCandidate]) -> ReconciliationMatch | None:
        scoped = [c for c in candidates if ReconciliationMatcher._identity_matches(broker, c)]
        if not scoped:
            return None
        if broker.client_order_id:
            exact = [c for c in scoped if c.client_order_id == broker.client_order_id]
            if len(exact) == 1:
                return ReconciliationMatch(exact[0].client_order_id, broker.broker_order_id, "CLIENT_ORDER_ID", broker.broker_account_id, broker.broker_route)
            if len(exact) > 1:
                return None
        broker_id = [c for c in scoped if c.broker_order_id == broker.broker_order_id]
        if len(broker_id) == 1:
            return ReconciliationMatch(broker_id[0].client_order_id, broker.broker_order_id, "BROKER_ORDER_ID", broker.broker_account_id, broker.broker_route)
        if len(broker_id) > 1:
            return None
        strict = [
            c for c in scoped
            if c.symbol.upper() == broker.symbol.upper()
            and c.side.upper() == broker.side.upper()
            and c.quantity == broker.quantity
            and abs((c.created_at - broker.timestamp).total_seconds()) <= 300
        ]
        if len(strict) == 1:
            return ReconciliationMatch(strict[0].client_order_id, broker.broker_order_id, "STRICT_ATTRIBUTES", broker.broker_account_id, broker.broker_route)
        return None
