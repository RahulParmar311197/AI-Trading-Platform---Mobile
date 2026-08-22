from datetime import datetime,timedelta,timezone
from app.execution_orchestrator import ExecutionOrchestrator
from app.trade_plan import TradePlanValidator,TradeAction
class FakeBroker:
 def __init__(self): self.calls=0
 def submit(self,plan): self.calls+=1; return 'TEST-ORDER-1'
def plan(minutes=60): return TradePlanValidator().build('NIFTY',TradeAction.BUY,100,95,110,10,100,minutes)
def test_live_and_kill_switch_are_required():
 b=FakeBroker(); o=ExecutionOrchestrator(b,False); assert not o.submit(plan(),True).accepted; assert b.calls==0
 o=ExecutionOrchestrator(b,True); assert not o.submit(plan(),False).accepted; assert b.calls==0

def test_valid_plan_reaches_broker():
 b=FakeBroker(); r=ExecutionOrchestrator(b,True).submit(plan(),True); assert r.accepted; assert r.order_id=='TEST-ORDER-1'; assert b.calls==1

def test_expired_plan_is_blocked():
 b=FakeBroker(); r=ExecutionOrchestrator(b,True).submit(plan(-1),True); assert not r.accepted; assert b.calls==0
