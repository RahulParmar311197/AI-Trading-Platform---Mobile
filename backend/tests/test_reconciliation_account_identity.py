from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect

from app.reconciliation_state_store import ReconciliationStateStore


class VerifiedResult:
    verified = True
    ok = True
    checked_at = datetime.now(timezone.utc).isoformat()
    order_drift = ()
    position_drift = ()


def test_opaque_account_ids_are_preserved_and_distinct(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}")
    store = ReconciliationStateStore(engine=engine)

    first = store.record_check(broker_account_id="001", broker_route="route-a", result=VerifiedResult())
    second = store.record_check(broker_account_id="1", broker_route="route-a", result=VerifiedResult())

    assert first.broker_account_id == "001"
    assert second.broker_account_id == "1"
    assert store.get_state(broker_account_id="001", broker_route="route-a").status == "VERIFIED"
    assert store.get_state(broker_account_id="1", broker_route="route-a").status == "VERIFIED"

    rows = inspect(engine).get_columns("reconciliation_states")
    account_column = next(column for column in rows if column["name"] == "broker_account_id")
    assert "CHAR" in str(account_column["type"]).upper() or "TEXT" in str(account_column["type"]).upper() or "VARCHAR" in str(account_column["type"]).upper()


def test_whitespace_is_canonicalized_but_distinct_ids_do_not_alias(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}")
    store = ReconciliationStateStore(engine=engine)

    result = store.record_check(broker_account_id="  acct-001  ", broker_route=" route-a ", result=VerifiedResult())

    assert result.broker_account_id == "acct-001"
    assert result.broker_route == "route-a"
    assert not store.is_trading_blocked(broker_account_id="acct-001", broker_route="route-a")
    assert store.is_trading_blocked(broker_account_id="acct-01", broker_route="route-a")
