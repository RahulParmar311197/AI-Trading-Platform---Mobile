from dataclasses import dataclass

@dataclass
class Leg:
    option_type:str
    side:str
    strike:float
    premium:float
    quantity:int=1
    lot_size:int=1

def leg_pnl(leg:Leg, spot:float)->float:
    intrinsic=max(0,spot-leg.strike) if leg.option_type.upper()=="CALL" else max(0,leg.strike-spot)
    sign=1 if leg.side.upper()=="BUY" else -1
    return sign*(intrinsic-leg.premium)*leg.quantity*leg.lot_size

def payoff(legs:list[Leg], spots:list[float])->dict:
    values=[sum(leg_pnl(l,s) for l in legs) for s in spots]
    return {"spots":spots,"pnl":values,"max_profit":max(values) if values else 0,"max_loss":min(values) if values else 0}
