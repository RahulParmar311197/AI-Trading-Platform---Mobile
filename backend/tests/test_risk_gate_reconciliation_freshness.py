from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, update

from app.broker_adapter import BrokerOrderRequest
from app.reconciliation import ReconciliationEngine
from app.reconciliation_state_store import ReconciliationStateStore
from app.risk_gate import PreTradeRiskGate, RiskLimits, RiskSnapshot


def _request() -> BrokerOrderRequest:
    return BrokerOrderRequest(
        client_order_id="client-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        broker_account_id=101,
        broker_route="upstox-primary",
    )


def _snapshot() -> RiskSnapshot:
    return RiskSnapshot(
        position_quantity=0,
        daily_pnl=0,
        projected_trade_loss=0,
        broker_ready=True,
    )


def _store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}")
    store = ReconciliationStateStore(engine=engine)
    ReconciliationEngine(state_store=store).check(
        [], [], [], [], broker_account_id=101, broker_route="upstox-primary"
    )
    return store


def test_fresh_verified_reconciliation_allows_risk_gate(tmp_path):
    store = _store(tmp_path)
    gate = PreTradeRiskGate(
        RiskLimits(max_order_quantity=10, max_position_quantity=10, max_daily_loss=1000, max_trade_loss=1000),
        reconciliation_state_store=store,
        reconciliation_max_age_seconds=30,
    )

    decision = gate.evaluate(_request(), _snapshot())

    assert decision == type(decision)(True, "RISK_OK")


def test_stale_verified_reconciliation_blocks_risk_gate(tmp_path):
    store = _store(tmp_path)
    stale = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with store.engine.begin() as connection:
        connection.execute(
            update(store.table)
            .where(
                store.table.c.broker_account_id == 101,
                store.table.c.broker_route == "upstox-primary",
            )
            .values(checked_at=stale, status="VERIFIED", trading_halted=False)
        )

    gate = PreTradeRiskGate(
        RiskLimits(max_order_quantity=10, max_position_quantity=10, max_daily_loss=1000, max_trade_loss=1000),
        reconciliation_state_store=store,
        reconciliation_max_age_seconds=30,
    )

    decision = gate.evaluate(_request(), _snapshot())

    assert not decision.allowed
    assert decision.reason == "RISK_RECONCILIATION_REQUIRED"


def test_malformed_verified_timestamp_fails_closed(tmp_path):
    store = _store(tmp_path)
    with store.engine.begin() as connection:
        connection.execute(
            update(store.table)
            .where(
                store.table.c.broker_account_id == 101,
                store.table.c.broker_route == "upstox-primary",
            )
            .values(checked_at="not-a-timestamp", status="VERIFIED", trading_halted=False)
        )

    gate = PreTradeRiskGate(
        RiskLimits(max_order_quantity=10, max_position_quantity=10, max_daily_loss=1000, max_trade_loss=1000),
        reconciliation_state_store=store,
    )

    decision = gate.evaluate(_request(), _snapshot())

    assert not decision.allowed
    assert decision.reason == "RISK_RECONCILIATION_REQUIRED"
