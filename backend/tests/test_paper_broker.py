from app.paper_broker import PaperBroker
from app.trade_plan import TradePlanValidator,TradeAction

def plan(): return TradePlanValidator().build('NIFTY',TradeAction.BUY,100,95,110,10,100)
def test_paper_order_and_mtm():
 b=PaperBroker(100000); oid=b.submit(plan()); assert oid.startswith('PAPER-'); assert b.get_order(oid).status=='FILLED'; assert b.mark_to_market(oid,105)==50

def test_invalid_cash_rejected():
 try: PaperBroker(0); assert False
 except ValueError: pass
