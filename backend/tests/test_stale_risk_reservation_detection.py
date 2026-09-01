from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.risk_reservation import RiskReservationRecord
from app.risk_reservation_store import RiskReservationStore


def _store(tmp_path: Path) -> RiskReservationStore:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'risk.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine, tables=[RiskReservationRecord.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return RiskReservationStore(Session)


def _reserve(store: RiskReservationStore, client_order_id: str, amount: float = 20) -> None:
    store.reserve(
        reservation_id=f"reservation-{client_order_id}",
        client_order_id=client_order_id,
        broker_account_id="001",
        broker_route="upstox:account:1",
        amount=amount,
        current_exposure=0,
        max_total_exposure=100,
    )


def test_stale_detection_is_read_only_and_returns_reason(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, "client-1")
    session = store._session_factory()
    try:
        record = session.get(RiskReservationRecord, "reservation-client-1")
        record.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session.commit()
    finally:
        session.close()

    as_of = datetime(2026, 1, 2, tzinfo=timezone.utc)
    candidates = store.stale_active_reservations(max_age=timedelta(hours=1), as_of=as_of)

    assert len(candidates) == 1
    assert candidates[0]["client_order_id"] == "client-1"
    assert candidates[0]["broker_account_id"] == "001"
    assert candidates[0]["broker_route"] == "upstox:account:1"
    assert candidates[0]["reason"] == "STALE_RISK_RESERVATION_REQUIRES_BROKER_RECONCILIATION"
    assert candidates[0]["age_seconds"] == 86400
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 20


def test_stale_detection_can_be_scoped_to_account_and_route(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, "client-1")
    session = store._session_factory()
    try:
        record = session.get(RiskReservationRecord, "reservation-client-1")
        record.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session.commit()
    finally:
        session.close()

    as_of = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert store.stale_active_reservations(
        max_age=timedelta(hours=1),
        as_of=as_of,
        broker_account_id="different-account",
        broker_route="upstox:account:1",
    ) == []
    assert store.stale_active_reservations(
        max_age=timedelta(hours=1),
        as_of=as_of,
        broker_account_id="001",
        broker_route="upstox:account:1",
    )[0]["client_order_id"] == "client-1"


def test_stale_detection_rejects_naive_as_of_and_negative_age(tmp_path: Path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="timezone-aware"):
        store.stale_active_reservations(
            max_age=timedelta(hours=1),
            as_of=datetime(2026, 1, 2),
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        store.stale_active_reservations(max_age=timedelta(seconds=-1))
