from app.execution import PaperBroker, OrderStatus
from app.execution_costs import ExecutionCostModel
from app.order_intent import OrderIntent


def test_paper_broker_applies_entry_cost_once():
    costs = ExecutionCostModel(fee_bps=10.0, slippage_bps=5.0)
    broker = PaperBroker(costs)
    order = OrderIntent("TEST", "BUY", 100.0, 95.0, 110.0, 10.0, 50.0, "test", 1.0)
    fill = broker.submit(order)
    assert fill.status == OrderStatus.FILLED
    assert fill.fill_price == 100.05
    assert fill.slippage == 0.5
    assert fill.commission == 0.10005
