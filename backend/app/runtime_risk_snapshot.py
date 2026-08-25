from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from time import time
from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRouter
from app.risk_gate import PreTradeRiskGate, RiskSnapshot

@dataclass(frozen=True)
class RuntimeRiskSnapshotProvider:
    router: BrokerRouter
    lifecycle: object
    trading_day_timezone: str = "Asia/Kolkata"
    max_snapshot_age_seconds: float = 2.0
    @staticmethod
    def _signed_position(row: dict) -> float:
        raw=row.get("net_quantity",row.get("netQty",row.get("quantity",row.get("qty",0))))
        try: quantity=float(raw)
        except (TypeError,ValueError) as exc: raise RuntimeError("invalid broker position quantity") from exc
        if not isfinite(quantity): raise RuntimeError("invalid broker position quantity")
        side=str(row.get("side","")).strip().upper()
        if side in {"BUY","LONG"} and quantity>=0: return quantity
        if side in {"SELL","SHORT"} and quantity>=0: return -quantity
        return quantity
    @classmethod
    def _position_for_request(cls,request,positions):
        symbol=str(request.symbol).upper(); security_id=str(request.security_id or ""); matches=[]
        for row in positions:
            row_symbol=str(row.get("symbol",row.get("tradingSymbol",row.get("tradingsymbol","")))).upper()
            row_security=str(row.get("security_id",row.get("securityId",row.get("instrument_token",row.get("instrumentToken","")))))
            if row_symbol==symbol or (security_id and row_security==security_id): matches.append(cls._signed_position(row))
        if len(matches)>1 and security_id and max(matches)-min(matches)>1e-9: raise RuntimeError("ambiguous broker position for requested instrument")
        return sum(matches)
    @staticmethod
    def _broker_ready(account):
        if not isinstance(account,dict) or not account: return False
        status=str(account.get("status",account.get("account_status",account.get("state","")))).strip().upper()
        return status not in {"DISABLED","BLOCKED","SUSPENDED","ERROR","NOT_READY"} and status in {"READY","ACTIVE","CONNECTED","OK",""}
    def _validate_freshness(self,snapshot):
        if not isfinite(float(self.max_snapshot_age_seconds)) or self.max_snapshot_age_seconds<=0: raise RuntimeError("invalid broker snapshot freshness configuration")
        fetched_at=getattr(snapshot,"fetched_at",None)
        if fetched_at is None: raise RuntimeError("broker snapshot has no freshness timestamp")
        try: age=time()-float(fetched_at)
        except (TypeError,ValueError) as exc: raise RuntimeError("invalid broker snapshot freshness timestamp") from exc
        if not isfinite(age) or age < -0.5 or age > self.max_snapshot_age_seconds: raise RuntimeError("broker risk snapshot is stale")
    def __call__(self,request:BrokerOrderRequest)->RiskSnapshot:
        if not request.broker_route: raise RuntimeError("broker account route is required for live risk authorization")
        if request.broker_account_id is None: raise RuntimeError("broker account id is required for live risk authorization")
        if self.router.safety_store is not None and self.router.safety_store.load().trading_halted: return RiskSnapshot(kill_switch=True,broker_ready=False)
        try:
            snapshot=self.router.get_snapshot(request.broker_route); self._validate_freshness(snapshot); account=self.router.get_account(request.broker_route)
        except Exception as exc: raise RuntimeError("live broker risk snapshot unavailable") from exc
        if snapshot.broker_route != request.broker_route or snapshot.broker_account_id is None or int(snapshot.broker_account_id) != int(request.broker_account_id):
            raise RuntimeError("broker risk snapshot account binding mismatch")
        position=self._position_for_request(request,snapshot.positions)
        if request.stop is None: raise RuntimeError("protective stop is required for live risk authorization")
        if request.price is None: raise RuntimeError("entry price is required to calculate projected trade loss")
        projected_loss=abs(float(request.price)-float(request.stop))*float(request.quantity)
        if not isfinite(projected_loss) or projected_loss<0: raise RuntimeError("invalid projected trade loss")
        return PreTradeRiskGate.snapshot_from_lifecycle(self.lifecycle,position_quantity=position,broker_ready=self._broker_ready(account),kill_switch=False,projected_trade_loss=projected_loss,trading_day_timezone=self.trading_day_timezone,broker_snapshot_fingerprint=snapshot.fingerprint())
