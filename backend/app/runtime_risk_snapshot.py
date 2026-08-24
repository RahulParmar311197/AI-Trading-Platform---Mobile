from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable

from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRouter
from app.risk_gate import PreTradeRiskGate, RiskSnapshot


@dataclass(frozen=True)
class RuntimeRiskSnapshotProvider:
    """Build a fail-closed, request-specific risk snapshot from live broker state."""

    router: BrokerRouter
    lifecycle: object
    trading_day_timezone: str = "UTC"
    projected_trade_loss_provider: Callable[[BrokerOrderRequest], float] | None = None

    @staticmethod
    def _signed_position(row: dict) -> float:
        raw = row.get("net_quantity", row.get("netQty", row.get("quantity", row.get("qty", 0))))
        try:
            quantity = float(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("invalid broker position quantity") from exc
        if not isfinite(quantity):
            raise RuntimeError("invalid broker position quantity")
        side = str(row.get("side", "")).strip().upper()
        if side in {"BUY", "LONG"} and quantity >= 0:
            return quantity
        if side in {"SELL", "SHORT"} and quantity >= 0:
            return -quantity
        return quantity

    @classmethod
    def _position_for_request(cls, request: BrokerOrderRequest, positions: list[dict]) -> float:
        symbol = str(request.symbol).upper()
        security_id = str(request.security_id or "")
        matches = []
        for row in positions:
            row_symbol = str(row.get("symbol", row.get("tradingSymbol", row.get("tradingsymbol", "")))).upper()
            row_security = str(row.get("security_id", row.get("securityId", row.get("instrument_token", row.get("instrumentToken", "")))))
            if row_symbol == symbol or (security_id and row_security == security_id):
                matches.append(cls._signed_position(row))
        if len(matches) > 1 and security_id:
            # Multiple records are valid only when they represent the same net position.
            if max(matches) - min(matches) > 1e-9:
                raise RuntimeError("ambiguous broker position for requested instrument")
        return sum(matches)

    @staticmethod
    def _broker_ready(account: dict) -> bool:
        if not isinstance(account, dict) or not account:
            return False
        status = str(account.get("status", account.get("account_status", account.get("state", "")))).strip().upper()
        if status in {"DISABLED", "BLOCKED", "SUSPENDED", "ERROR", "NOT_READY"}:
            return False
        return status in {"READY", "ACTIVE", "CONNECTED", "OK", ""}

    def __call__(self, request: BrokerOrderRequest) -> RiskSnapshot:
        if self.router.safety_store is not None and self.router.safety_store.load().trading_halted:
            return RiskSnapshot(kill_switch=True, broker_ready=False)
        if self.projected_trade_loss_provider is None:
            raise RuntimeError("projected trade loss provider is not configured")
        try:
            snapshot = self.router.get_snapshot()
            account = self.router.get_account()
            projected_loss = float(self.projected_trade_loss_provider(request))
        except Exception as exc:
            raise RuntimeError("live broker risk snapshot unavailable") from exc
        if not isfinite(projected_loss) or projected_loss < 0:
            raise RuntimeError("invalid projected trade loss")
        position = self._position_for_request(request, snapshot.positions)
        return PreTradeRiskGate.snapshot_from_lifecycle(
            self.lifecycle,
            position_quantity=position,
            broker_ready=self._broker_ready(account),
            kill_switch=False,
            projected_trade_loss=projected_loss,
            trading_day_timezone=self.trading_day_timezone,
        )
