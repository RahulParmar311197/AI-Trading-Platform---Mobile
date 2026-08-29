from sqlalchemy import create_engine

from app.broker_adapter import BrokerOrderRequest
from app.reconciliation import ReconciliationEngine
from app.reconciliation_state_store import ReconciliationStateStore
from app.risk_gate import PreTradeRiskGate, RiskLimits, RiskSnapshot


def request(account_id=101, route="upstox-primary"):
    return BrokerOrderRequest(
        client_order_id="risk-reconciliation-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        broker_account_id=account_id,
        broker_route=route,
    )


def gate(store):
    return PreTradeRiskGate(
        RiskLimits(max_order_quantity=10, max_position_quantity=20, max_daily_loss=1000, max_trade_loss=200),
        reconciliation_state_store=store,
    )


def ready():
    return RiskSnapshot(broker_ready=True)


def test_missing_reconciliation_state_blocks_order(tmp_path):
    store = ReconciliationStateStore(engine=create_engine(f"sqlite:///{tmp_path / 'risk.db'}"))
    result = gate(store).evaluate(request(), ready())
    assert not result.allowed
    assert result.reason == "RISK_RECONCILIATION_REQUIRED"


def test_halted_reconciliation_blocks_order(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'risk.db'}")
    store = ReconciliationStateStore(engine=engine)
    ReconciliationEngine(state_store=store).check(
        [], [], [{"symbol": "NIFTY", "quantity": 1}], [],
        broker_account_id=101,
        broker_route="upstox-primary",
    )
    result = gate(store).evaluate(request(), ready())
    assert not result.allowed
    assert result.reason == "RISK_RECONCILIATION_REQUIRED"


def test_clean_reconciliation_unblocks_only_matching_scope(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'risk.db'}")
    store = ReconciliationStateStore(engine=engine)
    reconciliation = ReconciliationEngine(state_store=store)
    reconciliation.check([], [], [{"symbol": "NIFTY", "quantity": 1}], [], broker_account_id=101, broker_route="upstox-primary")
    reconciliation.check([], [], [{"symbol": "NIFTY", "quantity": 2}], [], broker_account_id=202, broker_route="upstox-primary")
    reconciliation.check([], [], [], [], broker_account_id=101, broker_route="upstox-primary")

    allowed = gate(store).evaluate(request(101), ready())
    blocked = gate(store).evaluate(request(202), ready())
    assert allowed.allowed
    assert not blocked.allowed
    assert blocked.reason == "RISK_RECONCILIATION_REQUIRED"


def test_missing_account_scope_fails_closed(tmp_path):
    store = ReconciliationStateStore(engine=create_engine(f"sqlite:///{tmp_path / 'risk.db'}"))
    unsigned = BrokerOrderRequest(client_order_id="risk-unsigned", symbol="NIFTY", side="BUY", quantity=1)
    result = gate(store).evaluate(unsigned, ready())
    assert not result.allowed
    assert result.reason == "RISK_RECONCILIATION_REQUIRED"
