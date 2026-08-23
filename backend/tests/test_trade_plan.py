from app.trade_plan import TradeAction,TradePlanValidator

def test_valid_buy_plan():
 p=TradePlanValidator().build('NIFTY',TradeAction.BUY,100,95,110,10,100); assert p.risk_reward==2; assert p.quantity==10

def test_bad_direction_is_rejected():
 try: TradePlanValidator().build('NIFTY',TradeAction.BUY,100,105,110,10,100); assert False
 except ValueError: pass

def test_low_rr_is_rejected():
 try: TradePlanValidator().build('NIFTY',TradeAction.BUY,100,95,105,10,100); assert False
 except ValueError: pass
