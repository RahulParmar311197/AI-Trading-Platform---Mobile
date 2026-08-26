from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any
from app.order_intent import OrderIntent
from app.risk_gateway import RiskGatewayResult
from app.execution_costs import ExecutionCostModel
from app.idempotency import IdempotencyStore, InMemoryIdempotencyStore, claim_order
from app.broker_connectivity import BrokerConnectivitySupervisor

class OrderStatus(str, Enum):
    ACCEPTED='ACCEPTED'
    REJECTED='REJECTED'
    FILLED='FILLED'
    DUPLICATE='DUPLICATE'

@dataclass(frozen=True)
class ExecutionResult:
    order_id:str
    status:OrderStatus
    filled_quantity:float
    fill_price:float
    message:str
    commission:float = 0.0
    slippage:float = 0.0

class ExecutionAdapter:
    def submit(self, order: OrderIntent) -> ExecutionResult:
        raise NotImplementedError

class PaperBroker(ExecutionAdapter):
    def __init__(self, costs: ExecutionCostModel | None = None) -> None:
        self._counter=0
        self.costs=costs or ExecutionCostModel()

    def submit(self, order: OrderIntent) -> ExecutionResult:
        order = order.normalized()
        order.validate()
        self._counter += 1
        fill=self.costs.fill_price(order.side,order.entry)
        slip=abs(fill-order.entry)*order.quantity
        commission=self.costs.commission(fill,order.quantity)
        return ExecutionResult(f'PAPER-{self._counter:08d}',OrderStatus.FILLED,order.quantity,fill,'paper fill',commission,slip)

def _order_payload(order: OrderIntent) -> dict[str, Any]:
    return {
        'symbol': order.symbol,
        'side': order.side,
        'entry': order.entry,
        'stop_loss': order.stop_loss,
        'take_profit': order.take_profit,
        'quantity': order.quantity,
        'risk_amount': order.risk_amount,
        'source': order.source,
        'confidence': order.confidence,
    }

def execute_paper(
    *,
    risk: RiskGatewayResult,
    broker: PaperBroker | None = None,
    account_id: str = 'paper',
    broker_name: str = 'paper',
    request_id: str | None = None,
    idempotency_store: IdempotencyStore | None = None,
    connectivity: BrokerConnectivitySupervisor | None = None,
) -> ExecutionResult:
    if not risk.approved:
        return ExecutionResult('',OrderStatus.REJECTED,0.0,0.0,'risk gateway rejected order')
    if connectivity is not None and not connectivity.snapshot().can_trade:
        return ExecutionResult('',OrderStatus.REJECTED,0.0,0.0,'broker connectivity gate rejected order')
    order = risk.order.normalized()
    if request_id:
        store = idempotency_store or InMemoryIdempotencyStore()
        claim = claim_order(store,account_id=account_id,broker=broker_name,request_id=request_id,order=_order_payload(order))
        if claim.conflict:
            return ExecutionResult(f'IDEMPOTENCY-CONFLICT-{claim.fingerprint[:16]}',OrderStatus.REJECTED,0.0,0.0,'idempotency key was already used for a different order')
        if not claim.claimed:
            return ExecutionResult(f'IDEMPOTENT-{claim.fingerprint[:16]}',OrderStatus.DUPLICATE,0.0,0.0,'duplicate execution request rejected')
    return (broker or PaperBroker()).submit(order)
