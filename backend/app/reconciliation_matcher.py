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


@dataclass(frozen=True)
class BrokerOrderSnapshot:
    broker_order_id: str
    symbol: str
    side: str
    quantity: float
    timestamp: datetime
    client_order_id: str | None = None


@dataclass(frozen=True)
class ReconciliationMatch:
    client_order_id: str
    broker_order_id: str
    method: str


class ReconciliationMatcher:
    """Fail-closed deterministic matching; never chooses among ambiguous candidates."""

    @staticmethod
    def match(broker: BrokerOrderSnapshot, candidates: list[InternalOrderCandidate]) -> ReconciliationMatch | None:
        if broker.client_order_id:
            exact = [c for c in candidates if c.client_order_id == broker.client_order_id]
            if len(exact) == 1:
                return ReconciliationMatch(exact[0].client_order_id, broker.broker_order_id, "CLIENT_ORDER_ID")
            if len(exact) > 1:
                return None
        broker_id = [c for c in candidates if c.broker_order_id == broker.broker_order_id]
        if len(broker_id) == 1:
            return ReconciliationMatch(broker_id[0].client_order_id, broker.broker_order_id, "BROKER_ORDER_ID")
        if len(broker_id) > 1:
            return None
        strict = [
            c for c in candidates
            if c.symbol.upper() == broker.symbol.upper()
            and c.side.upper() == broker.side.upper()
            and c.quantity == broker.quantity
            and abs((c.created_at - broker.timestamp).total_seconds()) <= 300
        ]
        if len(strict) == 1:
            return ReconciliationMatch(strict[0].client_order_id, broker.broker_order_id, "STRICT_ATTRIBUTES")
        return None
