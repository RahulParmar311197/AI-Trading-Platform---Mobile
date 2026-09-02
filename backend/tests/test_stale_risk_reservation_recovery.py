from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.risk_reservation import RiskReservationRecord
from app.risk_reservation_store import RiskReservationStore


def _store(tmp_path: Path) -> RiskReservationStore:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'stale-risk.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine, tables=[RiskReservationRecord.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return RiskReservationStore(Session)


def _reserve_stale(store: RiskReservationStore, client_order_id: str = "client-1", amount: float = 20) -> str:
    reservation_id = f"reservation-{client_order_id}"
    store.reserve(
        reservation_id=reservation_id,
        client_order_id=client_order_id,
        broker_account_id="001",
        broker_route="upstox:account:1",
        amount=amount,
        current_exposure=50,
        max_total_exposure=100,
    )
    session = store._session_factory()
    try:
        with session.begin():
            record = session.get(RiskReservationRecord, reservation_id)
            record.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    finally:
        session.close()
    return reservation_id


def _broker_order(client_order_id: str, status: str) -> dict:
    return {
        "client_order_id": client_order_id,
        "broker_order_id": f"broker-{client_order_id}",
        "broker_account_id": "001",
        "broker_route": "upstox:account:1",
        "status": status,
    }


def test_stale_recovery_fails_when_authoritative_order_is_still_active(tmp_path: Path):
    store = _store(tmp_path)
    reservation_id = _reserve_stale(store)

    result = store.recover_stale_reservations(
        broker_orders=[_broker_order("client-1", "OPEN")],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(days=1),
        as_of=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )

    assert result["reconciled_reservation_ids"] == []
    assert result["failures"] == [
        {
            "id": reservation_id,
            "reason": "STALE_RISK_RESERVATION_STILL_ACTIVE_AFTER_RECONCILIATION",
        }
    ]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 20


def test_stale_recovery_completes_only_after_terminal_reconciliation(tmp_path: Path):
    store = _store(tmp_path)
    reservation_id = _reserve_stale(store)

    result = store.recover_stale_reservations(
        broker_orders=[_broker_order("client-1", "FILLED")],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(days=1),
        as_of=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )

    assert result["failures"] == []
    assert result["reconciled_reservation_ids"] == [reservation_id]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 0
