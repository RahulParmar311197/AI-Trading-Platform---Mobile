from sqlalchemy import create_engine

from app.reconciliation import ReconciliationEngine
from app.reconciliation_state_store import ReconciliationStateStore


def test_mismatch_persists_and_missing_state_fails_closed(tmp_path):
    database = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}")
    store = ReconciliationStateStore(engine=database)
    engine = ReconciliationEngine(state_store=store)

    failed = engine.check(
        [], [], [{"symbol": "NIFTY", "quantity": 1}], [],
        broker_account_id=101,
        broker_route="upstox-primary",
    )
    assert not failed.ok
    assert store.is_trading_blocked(broker_account_id=101, broker_route="upstox-primary")

    restarted_store = ReconciliationStateStore(engine=database)
    assert restarted_store.is_trading_blocked(broker_account_id=101, broker_route="upstox-primary")
    assert restarted_store.get_state(broker_account_id=101, broker_route="upstox-primary").status == "HALTED"


def test_clean_reconciliation_clears_only_matching_account_and_route(tmp_path):
    database = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}")
    store = ReconciliationStateStore(engine=database)
    engine = ReconciliationEngine(state_store=store)

    engine.check([], [], [{"symbol": "NIFTY", "quantity": 1}], [], broker_account_id=101, broker_route="route-a")
    engine.check([], [], [{"symbol": "NIFTY", "quantity": 2}], [], broker_account_id=202, broker_route="route-b")
    assert store.is_trading_blocked(broker_account_id=101, broker_route="route-a")
    assert store.is_trading_blocked(broker_account_id=202, broker_route="route-b")

    engine.check([], [], [], [], broker_account_id=101, broker_route="route-a")

    assert not store.is_trading_blocked(broker_account_id=101, broker_route="route-a")
    assert store.is_trading_blocked(broker_account_id=202, broker_route="route-b")


def test_unseen_account_is_blocked_after_restart(tmp_path):
    database = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}")
    store = ReconciliationStateStore(engine=database)
    assert store.is_trading_blocked(broker_account_id=303, broker_route="new-route")
    assert store.get_state(broker_account_id=303, broker_route="new-route").status == "UNKNOWN"


def test_durable_engine_requires_account_scope(tmp_path):
    database = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}")
    engine = ReconciliationEngine(state_store=ReconciliationStateStore(engine=database))
    try:
        engine.check([], [], [], [])
    except ValueError as exc:
        assert "broker account identity and route" in str(exc)
    else:
        raise AssertionError("durable reconciliation must require account scope")
