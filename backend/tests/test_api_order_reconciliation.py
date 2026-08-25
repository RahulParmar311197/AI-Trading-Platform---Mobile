from types import SimpleNamespace

from app.api_order_reconciliation import reconcile_api_order_projection
from app.order_lifecycle import OrderLifecycle, OrderStatus

class FakeQuery:
    def __init__(self, rows): self.rows = rows
    def all(self): return list(self.rows)
class FakeSession:
    def __init__(self, rows): self.rows = rows; self.commits = 0
    def query(self, model): return FakeQuery(self.rows)
    def add(self, row): self.rows.append(row)
    def commit(self): self.commits += 1

def _api_order(**overrides):
    values={"client_order_id":"ABC","user_id":7,"broker_account_id":1,"broker_route":"paper","status":"PENDING","broker_order_id":None,"symbol":"NIFTY","side":"BUY","order_type":"LIMIT","quantity":1.0,"price":22500.25,"stop":None,"security_id":"SEC-1","filled_quantity":0.0,"average_fill_price":None,"note":None,"id":1}; values.update(overrides); return SimpleNamespace(**values)

def _lifecycle():
    lifecycle=OrderLifecycle(); lifecycle.create("ABC","NIFTY","BUY",1,owner_user_id=7,broker_account_id=1,broker_route="paper",order_type="LIMIT",requested_price=22500.25,security_id="SEC-1"); return lifecycle

def test_projection_reconciles_existing_api_order_from_lifecycle():
    api_order=_api_order(); lifecycle=_lifecycle(); lifecycle.orders["ABC"].status=OrderStatus.FILLED; lifecycle.orders["ABC"].broker_order_id="BROKER-1"; lifecycle.orders["ABC"].filled_quantity=1.0; lifecycle.orders["ABC"].average_fill_price=22501.0
    db=FakeSession([api_order]); unresolved=reconcile_api_order_projection(db,lifecycle)
    assert unresolved==[]; assert api_order.status=="FILLED"; assert api_order.broker_order_id=="BROKER-1"; assert api_order.filled_quantity==1.0; assert api_order.average_fill_price==22501.0; assert api_order.price==22500.25; assert api_order.security_id=="SEC-1"; assert db.commits==1

def test_projection_does_not_create_or_submit_missing_lifecycle_order_and_blocks_startup():
    api_order=_api_order(); db=FakeSession([api_order]); unresolved=reconcile_api_order_projection(db,OrderLifecycle()); assert unresolved==["ABC:MISSING_EXECUTION_LIFECYCLE"]; assert api_order.status=="PENDING"; assert db.commits==0

def test_projection_materializes_owned_lifecycle_order_without_broker_side_effects():
    lifecycle=OrderLifecycle(); lifecycle.create("ABC","NIFTY","SELL",3,owner_user_id=42,broker_account_id=2,broker_route="paper",order_type="LIMIT",requested_price=22500.25,stop=22450.0,security_id="SEC-9"); lifecycle.orders["ABC"].status=OrderStatus.PARTIALLY_FILLED; lifecycle.orders["ABC"].broker_order_id="BROKER-9"; lifecycle.orders["ABC"].filled_quantity=1.0; lifecycle.orders["ABC"].average_fill_price=22499.5
    db=FakeSession([]); unresolved=reconcile_api_order_projection(db,lifecycle); assert unresolved==[]; assert db.commits==1; assert len(db.rows)==1; assert db.rows[0].user_id==42; assert db.rows[0].broker_account_id==2; assert db.rows[0].broker_route=="paper"; assert db.rows[0].client_order_id=="ABC"; assert db.rows[0].status=="PARTIALLY_FILLED"; assert db.rows[0].filled_quantity==1.0; assert db.rows[0].average_fill_price==22499.5

def test_projection_blocks_owner_mismatch():
    api_order=_api_order(); lifecycle=_lifecycle(); lifecycle.orders["ABC"].owner_user_id=8; db=FakeSession([api_order]); unresolved=reconcile_api_order_projection(db,lifecycle); assert unresolved==["ABC:EXECUTION_OWNER_MISMATCH"]; assert api_order.status=="PENDING"; assert db.commits==0

def test_projection_blocks_unowned_execution_lifecycle_order():
    lifecycle=OrderLifecycle(); lifecycle.create("ABC","NIFTY","BUY",1); db=FakeSession([]); unresolved=reconcile_api_order_projection(db,lifecycle); assert unresolved==["ABC:MISSING_EXECUTION_OWNER"]; assert db.rows==[]; assert db.commits==0

def test_projection_blocks_missing_broker_binding():
    lifecycle=OrderLifecycle(); lifecycle.create("ABC","NIFTY","BUY",1,owner_user_id=7); db=FakeSession([]); unresolved=reconcile_api_order_projection(db,lifecycle); assert unresolved==["ABC:MISSING_BROKER_ACCOUNT"]; assert db.rows==[]; assert db.commits==0
