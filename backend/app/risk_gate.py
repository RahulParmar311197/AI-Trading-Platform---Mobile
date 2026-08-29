from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.broker_adapter import BrokerOrderRequest
from app.order_lifecycle import OrderStatus


@dataclass(frozen=True)
class RiskLimits:
    max_order_quantity: float
    max_position_quantity: float
    max_daily_loss: float
    max_trade_loss: float


@dataclass(frozen=True)
class RiskSnapshot:
    position_quantity: float = 0.0
    daily_pnl: float = 0.0
    projected_trade_loss: float = 0.0
    kill_switch: bool = False
    broker_ready: bool = False
    broker_snapshot_fingerprint: str | None = None


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str


class ExposureReservationBook:
    """Atomic reservations rebuilt from durable lifecycle state after restart."""
    def __init__(self):
        self._lock = Lock()
        self._reservations: dict[str, float] = {}

    def reserve(self, client_order_id: str, signed_quantity: float, current_position: float, max_position: float) -> bool:
        with self._lock:
            existing = self._reservations.get(client_order_id)
            if existing is not None:
                return abs(existing - signed_quantity) <= 1e-9
            reserved = sum(self._reservations.values())
            projected = current_position + reserved + signed_quantity
            if abs(projected) > max_position + 1e-9:
                return False
            self._reservations[client_order_id] = signed_quantity
            return True

    def update(self, client_order_id: str, signed_quantity: float, current_position: float, max_position: float) -> bool:
        with self._lock:
            if client_order_id not in self._reservations:
                return False
            other_reserved = sum(v for k, v in self._reservations.items() if k != client_order_id)
            projected = current_position + other_reserved + signed_quantity
            if abs(projected) > max_position + 1e-9:
                return False
            if abs(signed_quantity) <= 1e-9:
                self._reservations.pop(client_order_id, None)
            else:
                self._reservations[client_order_id] = signed_quantity
            return True

    def rebuild_from_lifecycle(self, lifecycle) -> None:
        rebuilt: dict[str, float] = {}
        for order_id, order in lifecycle.orders.items():
            if order.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}:
                continue
            remaining = max(0.0, float(order.quantity) - float(order.filled_quantity))
            if remaining <= 1e-9:
                continue
            side = str(order.side).upper()
            sign = 1 if side == "BUY" else -1 if side == "SELL" else 0
            if sign == 0:
                raise RuntimeError(f"cannot rebuild risk reservation for invalid side: {side}")
            rebuilt[str(order_id)] = sign * remaining
        with self._lock:
            self._reservations = rebuilt

    def release(self, client_order_id: str) -> None:
        with self._lock:
            self._reservations.pop(client_order_id, None)

    def get(self, client_order_id: str) -> float | None:
        with self._lock:
            return self._reservations.get(client_order_id)

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return dict(self._reservations)


class PreTradeRiskGate:
    """Fail-closed authorization immediately before broker submission."""
    def __init__(self, limits: RiskLimits, reservations: ExposureReservationBook | None = None):
        if limits.max_order_quantity <= 0 or limits.max_position_quantity <= 0:
            raise ValueError("risk quantity limits must be positive")
        if limits.max_daily_loss < 0 or limits.max_trade_loss < 0:
            raise ValueError("risk loss limits cannot be negative")
        self.limits = limits
        self.reservations = reservations or ExposureReservationBook()

    @staticmethod
    def _side_sign(side: object) -> int:
        normalized = str(side or "").strip().upper()
        if normalized in {"BUY", "B", "LONG"}:
            return 1
        if normalized in {"SELL", "S", "SHORT"}:
            return -1
        return 0

    @staticmethod
    def trading_day_key(now: datetime | None = None, timezone_name: str = "UTC") -> str:
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"invalid trading-day timezone: {timezone_name}") from exc
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(zone).date().isoformat()

    @staticmethod
    def snapshot_from_lifecycle(lifecycle, position_quantity: float, broker_ready: bool, kill_switch: bool = False, projected_trade_loss: float = 0.0, trading_day: str | None = None, trading_day_timezone: str = "UTC", broker_snapshot_fingerprint: str | None = None) -> RiskSnapshot:
        if trading_day is None:
            trading_day = PreTradeRiskGate.trading_day_key(timezone_name=trading_day_timezone)
        else:
            PreTradeRiskGate.trading_day_key(timezone_name=trading_day_timezone)
        daily = lifecycle.realized_pnl_by_day.get(trading_day, 0.0)
        try:
            daily = float(daily)
            position = float(position_quantity)
            trade_loss = float(projected_trade_loss)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("invalid risk snapshot numeric value") from exc
        if daily != daily or daily in (float("inf"), float("-inf")):
            raise RuntimeError("invalid persisted daily realized pnl")
        if position != position or position in (float("inf"), float("-inf")):
            raise RuntimeError("invalid risk snapshot position")
        if trade_loss != trade_loss or trade_loss in (float("inf"), float("-inf")):
            raise RuntimeError("invalid risk snapshot trade loss")
        if broker_snapshot_fingerprint is not None and not str(broker_snapshot_fingerprint).strip():
            raise RuntimeError("invalid broker snapshot fingerprint")
        return RiskSnapshot(position_quantity=position, daily_pnl=daily, projected_trade_loss=trade_loss, kill_switch=bool(kill_switch), broker_ready=bool(broker_ready), broker_snapshot_fingerprint=broker_snapshot_fingerprint)

    def evaluate(self, request: BrokerOrderRequest, snapshot: RiskSnapshot) -> RiskDecision:
        if snapshot.kill_switch:
            return RiskDecision(False, "RISK_KILL_SWITCH_ACTIVE")
        if not snapshot.broker_ready:
            return RiskDecision(False, "RISK_BROKER_NOT_READY")
        try:
            quantity = float(request.quantity)
        except (TypeError, ValueError):
            return RiskDecision(False, "RISK_INVALID_QUANTITY")
        if quantity <= 0:
            return RiskDecision(False, "RISK_INVALID_QUANTITY")
        if quantity > self.limits.max_order_quantity:
            return RiskDecision(False, "RISK_MAX_ORDER_QUANTITY")
        side_sign = self._side_sign(request.side)
        if side_sign == 0:
            return RiskDecision(False, "RISK_INVALID_SIDE")
        current_position = float(snapshot.position_quantity)
        projected_position = current_position + side_sign * quantity
        if abs(projected_position) > self.limits.max_position_quantity + 1e-9:
            return RiskDecision(False, "RISK_MAX_POSITION_QUANTITY")
        if -float(snapshot.daily_pnl) >= self.limits.max_daily_loss:
            return RiskDecision(False, "RISK_DAILY_LOSS_LIMIT")
        if float(snapshot.projected_trade_loss) > self.limits.max_trade_loss + 1e-9:
            return RiskDecision(False, "RISK_TRADE_LOSS_LIMIT")
        return RiskDecision(True, "RISK_OK")

    def reserve(self, request: BrokerOrderRequest, snapshot: RiskSnapshot) -> RiskDecision:
        decision = self.evaluate(request, snapshot)
        if not decision.allowed:
            return decision
        signed = self._side_sign(request.side) * float(request.quantity)
        if not self.reservations.reserve(request.client_order_id, signed, float(snapshot.position_quantity), self.limits.max_position_quantity):
            return RiskDecision(False, "RISK_EXPOSURE_RESERVATION")
        return RiskDecision(True, "RISK_OK")

    def update_after_fill(self, request: BrokerOrderRequest, filled_quantity: float, current_position: float) -> RiskDecision:
        remaining = max(0.0, float(request.quantity) - float(filled_quantity))
        signed_remaining = self._side_sign(request.side) * remaining
        if not self.reservations.update(request.client_order_id, signed_remaining, current_position, self.limits.max_position_quantity):
            return RiskDecision(False, "RISK_EXPOSURE_RESERVATION_UPDATE")
        return RiskDecision(True, "RISK_OK")

    def rebuild_from_lifecycle(self, lifecycle) -> None:
        self.reservations.rebuild_from_lifecycle(lifecycle)

    def release(self, client_order_id: str) -> None:
        self.reservations.release(client_order_id)


@dataclass(frozen=True)
class RiskGateDecision:
    approved: bool
    checks: dict[str, bool]


class RiskGate:
    """Compatibility facade for lightweight portfolio-level execution checks."""
    def __init__(self, max_gross_exposure: float, max_positions: int):
        self.max_gross_exposure = float(max_gross_exposure)
        self.max_positions = int(max_positions)

    def evaluate(self, portfolio, requested_notional: float) -> RiskGateDecision:
        exposure_ok = self.max_gross_exposure > 0 and float(requested_notional) <= self.max_gross_exposure
        positions = getattr(portfolio, "positions", None)
        position_count_ok = positions is not None and len(positions) < self.max_positions
        checks = {"exposure_limit": exposure_ok, "position_count_limit": position_count_ok}
        return RiskGateDecision(approved=all(checks.values()), checks=checks)
