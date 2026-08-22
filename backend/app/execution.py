from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.order_intent import OrderIntent
from app.risk_gateway import RiskGatewayResult

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

class ExecutionAdapter:
    def submit(self, order: OrderIntent) -> ExecutionResult:
        raise NotImplementedError

class PaperBroker(ExecutionAdapter):
    def __init__(self) -> None:
        self._counter=0

    def submit(self, order: OrderIntent) -> ExecutionResult:
        order.validate()
        self._counter += 1
        return ExecutionResult(f'PAPER-{self._counter:08d}',OrderStatus.FILLED,order.quantity,order.entry,'paper fill')

def execute_paper(*, risk: RiskGatewayResult, broker: PaperBroker | None = None) -> ExecutionResult:
    if not risk.approved:
        return ExecutionResult('','REJECTED',0.0,0.0,'risk gateway rejected order')
    return (broker or PaperBroker()).submit(risk.order)
