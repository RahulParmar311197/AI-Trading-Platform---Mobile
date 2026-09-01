from __future__ import annotations

import os
from threading import Barrier, Lock, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from app.reconciliation_state_store import ReconciliationStateStore


@pytest.mark.integration
def test_postgres_concurrent_record_checks_are_atomic():
    """Concurrent writers for one account/route must not race on the state row."""
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is not configured")

    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        pytest.skip("TEST_POSTGRES_URL must point to PostgreSQL")

    account = f"recon-concurrency-{uuid4()}"
    route = f"route-{uuid4()}"
    barrier = Barrier(2)
    outcome_lock = Lock()
    errors: list[Exception] = []

    result_a = SimpleNamespace(
        verified=True,
        ok=True,
        checked_at="2026-09-02T00:00:00+00:00",
        order_drift=[],
        position_drift=[],
    )
    result_b = SimpleNamespace(
        verified=True,
        ok=False,
        checked_at="2026-09-02T00:00:01+00:00",
        order_drift=[{"id": "drift"}],
        position_drift=[],
    )

    def worker(result) -> None:
        store = ReconciliationStateStore(engine=engine)
        barrier.wait()
        try:
            store.record_check(
                broker_account_id=account,
                broker_route=route,
                result=result,
            )
        except Exception as exc:  # pragma: no cover - asserted below
            with outcome_lock:
                errors.append(exc)

    threads = [Thread(target=worker, args=(result_a,)), Thread(target=worker, args=(result_b,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    try:
        assert all(not thread.is_alive() for thread in threads), "reconciliation state writer deadlocked"
        assert errors == []
        state = ReconciliationStateStore(engine=engine).get_state(
            broker_account_id=account,
            broker_route=route,
        )
        assert state.broker_account_id == account
        assert state.broker_route == route
        assert state.status in {"VERIFIED", "HALTED"}
        assert state.checked_at in {
            result_a.checked_at,
            result_b.checked_at,
        }
        assert state.order_drift_count in {0, 1}
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "DELETE FROM reconciliation_states WHERE broker_account_id = %s AND broker_route = %s",
                (account, route),
            )
        engine.dispose()
