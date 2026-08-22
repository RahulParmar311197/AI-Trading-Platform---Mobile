from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PositionSizeResult:
    quantity:int; risk_amount:float; stop_distance:float; max_loss:float; valid:bool; reasons:tuple[str,...]

class RiskPositionSizer:
    def __init__(self,max_risk_pct:float=1.0,max_position_value_pct:float=20.0):
        if max_risk_pct<=0 or max_position_value_pct<=0: raise ValueError('risk limits must be positive')
        self.max_risk_pct=max_risk_pct; self.max_position_value_pct=max_position_value_pct
    def size(self,equity:float,entry:float,stop:float,contract_multiplier:float=1.0)->PositionSizeResult:
        if equity<=0 or entry<=0 or stop<=0 or contract_multiplier<=0:return PositionSizeResult(0,0,0,0,False,('INVALID_INPUT',))
        distance=abs(entry-stop)
        if distance==0:return PositionSizeResult(0,0,0,0,False,('STOP_DISTANCE_ZERO',))
        risk_amount=equity*self.max_risk_pct/100; risk_per_unit=distance*contract_multiplier; qty=int(risk_amount/risk_per_unit)
        max_value=equity*self.max_position_value_pct/100; qty=min(qty,int(max_value/(entry*contract_multiplier)))
        reasons=[]
        if qty<1: reasons.append('RISK_LIMIT_TOO_SMALL_FOR_ONE_UNIT')
        max_loss=qty*risk_per_unit
        if max_loss>risk_amount+1e-9: reasons.append('MAX_LOSS_EXCEEDED')
        return PositionSizeResult(qty,risk_amount,distance,max_loss,not reasons,tuple(reasons) if reasons else ('RISK_CHECK_PASSED',))
