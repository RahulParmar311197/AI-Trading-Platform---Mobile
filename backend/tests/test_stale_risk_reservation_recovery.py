from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.risk_reservation import RiskReservationRecord
from app.risk_reservation_store import RiskReservationStore
from app.trading_audit import TradingAuditLog


def _store(tmp_path: Path, audit_log: TradingAuditLog | None = None) -> RiskReservationStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'risk.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[RiskReservationRecord.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return RiskReservationStore(Session, audit_log=audit_log)


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


def _age(store: RiskReservationStore, client_order_id: str) -> None:
    session = store._session_factory()
    try:
        record = session.query(RiskReservationRecord).filter_by(client_order_id=client_order_id).one()
        record.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session.commit()
    finally:
        session.close()


def _broker_order(client_order_id: str, status: str, *, remaining_exposure: float | None = None) -> dict:
    order = {
        "client_order_id": client_order_id,
        "broker_order_id": f"broker-{client_order_id}",
        "broker_account_id": "001",
        "broker_route": "upstox:account:1",
        "status": status,
    }
    if remaining_exposure is not None:
        order["remaining_exposure"] = remaining_exposure
    return order


def test_stale_recovery_releases_only_after_authoritative_terminal_match(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, "client-1")
    _age(store, "client-1")

    result = store.recover_stale_reservations(
        broker_orders=[_broker_order("client-1", "FILLED")],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(hours=1),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result["failures"] == []
    assert result["reconciled_reservation_ids"] == ["reservation-client-1"]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 0


def test_stale_recovery_keeps_reservation_when_authoritative_match_is_missing(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, "client-1")
    _age(store, "client-1")

    result = store.recover_stale_reservations(
        broker_orders=[],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(hours=1),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result["failures"][0]["reason"] == "RISK_RESERVATION_BROKER_MATCH_MISSING"
    assert result["reconciled_reservation_ids"] == []
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 20


def test_stale_recovery_is_atomic_when_an_unrelated_broker_order_is_orphaned(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, "client-1")
    _reserve(store, "client-2")
    _age(store, "client-1")
    _age(store, "client-2")

    result = store.recover_stale_reservations(
        broker_orders=[
            _broker_order("client-1", "FILLED"),
            _broker_order("orphan", "OPEN"),
        ],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(hours=1),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result["failures"][0]["reason"] == "RISK_RESERVATION_ORPHAN_BROKER_ORDER"
    assert result["reconciled_reservation_ids"] == []
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 40


def test_stale_recovery_partial_fill_only_shrinks_reservation(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, "client-1", amount=20)
    _age(store, "client-1")

    result = store.recover_stale_reservations(
        broker_orders=[_broker_order("client-1", "PARTIALLY_FILLED", remaining_exposure=15)],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(hours=1),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result["failures"] == []
    assert result["reconciled_reservation_ids"] == []
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 15


def test_stale_detection_and_recovery_emit_audit_events(tmp_path: Path):
    audit_path = tmp_path / "trading-audit.jsonl"
    audit_log = TradingAuditLog(str(audit_path))
    store = _store(tmp_path, audit_log=audit_log)
    _reserve(store, "client-1")
    _age(store, "client-1")

    result = store.recover_stale_reservations(
        broker_orders=[_broker_order("client-1", "FILLED")],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(hours=1),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result["failures"] == []
    events = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(events) == 2
    assert '"event_type":"STALE_RISK_RESERVATIONS_DETECTED"' in events[0]
    assert '"event_type":"STALE_RISK_RESERVATION_RECOVERY_COMPLETED"' in events[1]


def test_stale_recovery_failure_emits_audit_event_and_keeps_exposure(tmp_path: Path):
    audit_path = tmp_path / "trading-audit.jsonl"
    audit_log = TradingAuditLog(str(audit_path))
    store = _store(tmp_path, audit_log=audit_log)
    _reserve(store, "client-1")
    _age(store, "client-1")

    result = store.recover_stale_reservations(
        broker_orders=[],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(hours=1),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result["failures"]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 20
    events = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line]
    assert '"event_type":"STALE_RISK_RESERVATION_RECOVERY_FAILED"' in events[-1]


def test_stale_recovery_fails_when_authoritative_order_is_still_active(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, "client-1")
    _age(store, "client-1")

    result = store.recover_stale_reservations(
        broker_orders=[_broker_order("client-1", "OPEN")],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(hours=1),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result["reconciled_reservation_ids"] == []
    assert result["failures"] == [
        {
            "id": "reservation-client-1",
            "reason": "STALE_RISK_RESERVATION_STILL_ACTIVE_AFTER_RECONCILIATION",
        }
    ]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 20


def test_stale_recovery_does_not_emit_completed_audit_when_reservation_remains_active(tmp_path: Path):
    audit_path = tmp_path / "trading-audit.jsonl"
    audit_log = TradingAuditLog(str(audit_path))
    store = _store(tmp_path, audit_log=audit_log)
    _reserve(store, "client-1")
    _age(store, "client-1")

    result = store.recover_stale_reservations(
        broker_orders=[_broker_order("client-1", "OPEN")],
        broker_account_id="001",
        broker_route="upstox:account:1",
        max_age=timedelta(hours=1),
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result["failures"]
    events = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line]
    assert '"event_type":"STALE_RISK_RESERVATION_RECOVERY_FAILED"' in events[-1]
    assert all('"event_type":"STALE_RISK_RESERVATION_RECOVERY_COMPLETED"' not in line for line in events)
