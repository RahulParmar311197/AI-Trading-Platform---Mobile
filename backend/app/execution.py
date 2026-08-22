from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.order_intent import OrderIntent
from app.risk_gateway import RiskGatewayResult
from app.execution_costs import ExecutionCostModel

class OrderStatus(str, Enum):
    ACCEPTED='ACCEPTED'
    REJECTED='REJECTED'
    FILLED='FILLED'

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
        order.validate()
        self._counter += 1
        fill=self.costs.fill_price(order.side,order.entry)
        slip=abs(fill-order.entry)*order.quantity
        commission=self.costs.commission(fill,order.quantity)
        return ExecutionResult(f'PAPER-{self._counter:08d}',OrderStatus.FILLED,order.quantity,fill,'paper fill',commission,slip)

def execute_paper(*, risk: RiskGatewayResult, broker: PaperBroker | None = None) -> ExecutionResult:
    if not risk.approved:
        return ExecutionResult('','REJECTED',0.0,0.0,'risk gateway rejected order')
    return (broker or PaperBroker()).submit(risk.order)
