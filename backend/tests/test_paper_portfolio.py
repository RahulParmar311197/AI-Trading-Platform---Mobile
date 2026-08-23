from app.paper_portfolio import PaperPortfolio
from app.trade_plan import TradePlanValidator,TradeAction

def plan(): return TradePlanValidator().build('NIFTY',TradeAction.BUY,100,95,110,10,100)
def test_stop_loss_closes_trade_and_updates_equity():
 p=PaperPortfolio(100000,fee_per_order=2); oid=p.open(plan()); closed=p.update({'NIFTY':94}); assert closed[0].reason=='STOP_LOSS'; assert closed[0].pnl==-52; assert not p.open_ids; assert p.equity({})==99946

def test_take_profit_closes_trade():
 p=PaperPortfolio(100000); p.open(plan()); closed=p.update({'NIFTY':110}); assert closed[0].reason=='TAKE_PROFIT'; assert closed[0].pnl==100

def test_unrealized_pnl():
 p=PaperPortfolio(100000); p.open(plan()); assert p.unrealized_pnl({'NIFTY':105})==50
