from __future__ import annotations

from dataclasses import dataclass
import math

from app.ai_decision_engine import TradingDecision
from app.broker_adapter import BrokerOrderRequest
from app.instruments import InstrumentProvider
from app.position_sizing import calculate_position_size


@dataclass(frozen=True)
class AITradeIntentConfig:
    risk_fraction: float = 0.01
    max_quantity: int | None = None
    order_type: str = "MARKET"
    product_type: str = "CNC"
    validity: str = "DAY"


def build_ai_order_request(
    decision: TradingDecision,
    *,
    equity: float,
    client_order_id: str,
    instrument_provider: InstrumentProvider,
    config: AITradeIntentConfig | None = None,
    owner_user_id: int | None = None,
    broker_account_id: str | None = None,
    broker_route: str | None = None,
    broker_route_generation: str | None = None,
) -> BrokerOrderRequest | None:
    """Convert an AI trade decision into a fully sized order request.

    HOLD and invalid trade decisions return no executable request. Broker/risk
    authorization remains the responsibility of OrderExecutionService.
    """
    cfg = config or AITradeIntentConfig()
    if not client_order_id.strip():
        raise ValueError("client_order_id is required")
    if broker_account_id is not None:
        if isinstance(broker_account_id, bool) or not str(broker_account_id).strip():
            raise ValueError("broker_account_id must be a non-empty string")
        if len(str(broker_account_id).strip()) > 128:
            raise ValueError("broker_account_id exceeds 128 characters")
        broker_account_id = str(broker_account_id).strip()
    if not math.isfinite(float(equity)) or equity <= 0:
        raise ValueError("equity must be positive and finite")
    if not 0 < cfg.risk_fraction <= 1:
        raise ValueError("risk_fraction must be in (0, 1]")
    if decision.decision == "HOLD":
        return None
    if decision.decision not in {"BUY", "SELL"}:
        raise ValueError("unsupported trading decision")
    if decision.entry is None or decision.stop_loss is None:
        raise ValueError("trade decision requires entry and stop_loss")
    if decision.target is None:
        raise ValueError("trade decision requires target")
    for name, value in (("entry", decision.entry), ("stop_loss", decision.stop_loss), ("target", decision.target)):
        if not math.isfinite(float(value)) or float(value) <= 0:
            raise ValueError(f"{name} must be positive and finite")
    if decision.decision == "BUY" and not (decision.stop_loss < decision.entry < decision.target):
        raise ValueError("BUY requires stop < entry < target")
    if decision.decision == "SELL" and not (decision.target < decision.entry < decision.stop_loss):
        raise ValueError("SELL requires target < entry < stop")

    symbol = getattr(decision, "symbol", None)
    if not symbol:
        raise ValueError("TradingDecision does not carry symbol; provide a symbol-aware decision contract")
    instrument = instrument_provider.resolve(symbol)
    if instrument is None:
        raise ValueError(f"instrument metadata unavailable for {symbol}")
    size = calculate_position_size(
        equity=equity,
        risk_fraction=cfg.risk_fraction,
        entry=float(decision.entry),
        stop=float(decision.stop_loss),
        instrument=instrument,
        max_quantity=cfg.max_quantity,
    )
    return BrokerOrderRequest(
        client_order_id=client_order_id,
        symbol=instrument.symbol,
        side=decision.decision,
        quantity=size.quantity,
        order_type=cfg.order_type,
        price=float(decision.entry),
        stop=float(decision.stop_loss),
        target=float(decision.target),
        security_id=instrument.security_id,
        exchange_segment=instrument.exchange_segment,
        product_type=cfg.product_type,
        validity=cfg.validity,
        owner_user_id=owner_user_id,
        broker_account_id=broker_account_id,
        broker_route=broker_route,
        broker_route_generation=broker_route_generation,
    )
