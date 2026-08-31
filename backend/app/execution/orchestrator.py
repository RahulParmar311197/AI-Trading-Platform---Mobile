from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from app.brokers.base import BrokerAdapter
from .risk_gate import RiskGate
from .sql_repository import ExecutionRepository


@dataclass(frozen=True)
class ExecutionRequest:
    client_order_id: str
    route: str
    account_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    price: float | None = None
    stop: float | None = None


class ExecutionOrchestrator:
    """Provider-neutral, fail-closed broker submission boundary."""

    def __init__(self, broker: BrokerAdapter, repository: ExecutionRepository, risk_gate: RiskGate, clock=None):
        self._broker = broker
        self._repository = repository
        self._risk_gate = risk_gate
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def fingerprint(request: ExecutionRequest) -> str:
        raw = "|".join(map(str, (request.client_order_id, request.route, request.account_id, request.symbol, request.side, request.quantity, request.order_type, request.price, request.stop)))
        return sha256(raw.encode()).hexdigest()

    def submit(self, request: ExecutionRequest) -> dict[str, Any]:
        decision = self._risk_gate.authorize(quantity=request.quantity, price=request.price, order_type=request.order_type)
        if not decision.approved:
            return {"status": "REJECTED", "reason": decision.reason, "idempotent": False}

        fingerprint = self.fingerprint(request)
        existing = self._repository.get_intent(request.client_order_id)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise ValueError("client_order_id is already bound to a different order")
            if existing.broker_order_id:
                return {"status": existing.broker_status or "SUBMITTED", "broker_order_id": existing.broker_order_id, "idempotent": True}
            raise RuntimeError("ambiguous prior broker submission; reconcile before retrying")

        self._repository.create_intent(
            client_order_id=request.client_order_id, route=request.route,
            account_id=request.account_id, symbol=request.symbol, side=request.side,
            quantity=request.quantity, request_fingerprint=fingerprint, created_at=self._clock(),
        )
        self._repository.reserve(
            client_order_id=request.client_order_id, broker_account_id=request.account_id,
            broker_route=request.route, amount=request.quantity * (request.price or 0), created_at=self._clock(),
        )
        self._repository.session.commit()

        result = self._broker.place_order({
            "client_order_id": request.client_order_id, "symbol": request.symbol,
            "side": request.side, "quantity": request.quantity,
            "order_type": request.order_type, "price": request.price, "stop": request.stop,
        })
        broker_order_id = result.get("broker_order_id") or result.get("order_id")
        if not broker_order_id:
            raise RuntimeError("broker returned no durable order identifier")
        self._repository.resolve_intent(request.client_order_id, broker_order_id, result.get("status"))
        self._repository.session.commit()
        return {**result, "broker_order_id": broker_order_id, "idempotent": False}
