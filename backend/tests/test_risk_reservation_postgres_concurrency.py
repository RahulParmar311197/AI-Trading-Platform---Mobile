from __future__ import annotations

import os
from threading import Barrier, Lock, Thread
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.risk_reservation import RiskReservationRecord
from app.risk_reservation_store import RiskReservationStore


@pytest.mark.integration
def test_postgres_serializes_concurrent_reservations():
    """Two workers cannot both consume the same remaining exposure budget."""
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is not configured")

    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        pytest.skip("TEST_POSTGRES_URL must point to PostgreSQL")

    Base.metadata.create_all(bind=engine, tables=[RiskReservationRecord.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    account = f"concurrency-{uuid4()}"
    route = "upstox"
    client_ids = [f"client-{uuid4()}", f"client-{uuid4()}"]
    reservation_ids = [f"reservation-{uuid4()}", f"reservation-{uuid4()}"]
    barrier = Barrier(2)
    outcome_lock = Lock()
    outcomes: list[str] = []

    def worker(index: int) -> None:
        store = RiskReservationStore(Session)
        barrier.wait()
        try:
            store.reserve(
                reservation_id=reservation_ids[index],
                client_order_id=client_ids[index],
                broker_account_id=account,
                broker_route=route,
                amount=10,
                current_exposure=90,
                max_total_exposure=100,
            )
        except RuntimeError as exc:
            outcome = f"rejected:{exc}"
        else:
            outcome = "accepted"
        with outcome_lock:
            outcomes.append(outcome)

    threads = [Thread(target=worker, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    try:
        assert all(not thread.is_alive() for thread in threads), "reservation worker deadlocked"
        assert len(outcomes) == 2
        assert sum(status == "accepted" for status in outcomes) == 1
        assert sum(status.startswith("rejected:") for status in outcomes) == 1
        assert RiskReservationStore(Session).active_amount(
            broker_account_id=account, broker_route=route
        ) == 10
    finally:
        with Session.begin() as session:
            session.execute(
                delete(RiskReservationRecord).where(
                    RiskReservationRecord.broker_account_id == account,
                    RiskReservationRecord.broker_route == route,
                )
            )
        engine.dispose()
