from app.broker_adapter import BrokerOrderRequest
from app.order_lifecycle import OrderLifecycle
from app.risk_gate import RiskGate

class P:
    positions=[]

def test_risk_gate_rejects_excessive_requested_notional():
    gate=RiskGate(max_gross_exposure=1000,max_positions=50)
    decision=gate.evaluate(P(),requested_notional=1001)
    assert decision.approved is False
    assert decision.checks["exposure_limit"] is False

def test_risk_gate_allows_small_request():
    gate=RiskGate(max_gross_exposure=1000,max_positions=50)
    decision=gate.evaluate(P(),requested_notional=100)
    assert decision.approved is True

def test_lifecycle_preserves_execution_metadata():
    lifecycle=OrderLifecycle()
    req=BrokerOrderRequest(client_order_id="safe-1",symbol="NIFTY",side="BUY",quantity=1,order_type="LIMIT",price=25000,stop=24900,target=25200,security_id="123",exchange_segment="NSE_FO",product_type="I",validity="DAY",trigger_price=24950)
    lifecycle.create(req.client_order_id,req.symbol,req.side,req.quantity,order_type=req.order_type,requested_price=req.price,stop=req.stop,target=req.target,security_id=req.security_id,exchange_segment=req.exchange_segment,product_type=req.product_type,validity=req.validity,trigger_price=req.trigger_price)
    order=lifecycle.orders[req.client_order_id]
    assert order.stop==24900 and order.target==25200 and order.security_id=="123"
