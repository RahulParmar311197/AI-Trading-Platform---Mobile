from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.submission_intent import SubmissionIntentRecord
from app.startup_migrations import migrate_legacy_submission_intents


def _write_intents(path: Path, *, client_order_id: str = "cli-1", account_id: str = "001") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "{\n"
        f'  "{client_order_id}": {{\n'
        '    "client_order_id": "' + client_order_id + '",\n'
        '    "route": "upstox",\n'
        f'    "account_id": "{account_id}",\n'
        '    "symbol": "NIFTY",\n'
        '    "side": "BUY",\n'
        '    "quantity": 10,\n'
        '    "request_fingerprint": "fp-1",\n'
        '    "created_at": "2026-08-30T10:00:00+00:00",\n'
        '    "resolved_at": null\n'
        "  }\n"
        "}\n",
        encoding="utf-8",
    )


def _session_factory(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'intents.db'}")
    Base.metadata.create_all(engine, tables=[SubmissionIntentRecord.__table__])
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_migrates_unresolved_legacy_intent_and_archives_source(tmp_path: Path):
    path = tmp_path / "data" / "submission_intents.json"
    _write_intents(path)
    Session = _session_factory(tmp_path)

    count = migrate_legacy_submission_intents(Session, path=str(path))

    assert count == 1
    assert not path.exists()
    assert (tmp_path / "data" / "submission_intents.json.migrated").exists()
    with Session() as session:
        row = session.get(SubmissionIntentRecord, "cli-1")
        assert row is not None
        assert row.account_id == "001"
        assert row.resolved_at is None


def test_matching_existing_unresolved_intent_is_idempotent(tmp_path: Path):
    path = tmp_path / "submission_intents.json"
    _write_intents(path)
    Session = _session_factory(tmp_path)
    with Session.begin() as session:
        session.add(
            SubmissionIntentRecord(
                client_order_id="cli-1",
                route="upstox",
                account_id="001",
                symbol="NIFTY",
                side="BUY",
                quantity=10,
                request_fingerprint="fp-1",
                created_at=datetime(2026, 8, 30, 10, tzinfo=timezone.utc),
            )
        )

    assert migrate_legacy_submission_intents(Session, path=str(path)) == 1
    assert not path.exists()


def test_conflicting_existing_resolved_intent_fails_closed_and_keeps_legacy_file(tmp_path: Path):
    path = tmp_path / "submission_intents.json"
    _write_intents(path)
    Session = _session_factory(tmp_path)
    with Session.begin() as session:
        session.add(
            SubmissionIntentRecord(
                client_order_id="cli-1",
                route="upstox",
                account_id="001",
                symbol="NIFTY",
                side="BUY",
                quantity=10,
                request_fingerprint="fp-1",
                created_at=datetime(2026, 8, 30, 10, tzinfo=timezone.utc),
                resolved_at=datetime.now(timezone.utc),
            )
        )

    with pytest.raises(RuntimeError, match="conflicting durable submission intent"):
        migrate_legacy_submission_intents(Session, path=str(path))
    assert path.exists()
    assert not (tmp_path / "submission_intents.json.migrated").exists()


def test_corrupt_legacy_file_fails_closed_and_is_not_archived(tmp_path: Path):
    path = tmp_path / "submission_intents.json"
    path.write_text("{corrupt", encoding="utf-8")
    Session = _session_factory(tmp_path)

    with pytest.raises(RuntimeError, match="invalid persisted submission intent state"):
        migrate_legacy_submission_intents(Session, path=str(path))

    assert path.exists()
    assert not (tmp_path / "submission_intents.json.migrated").exists()


def test_database_failure_keeps_legacy_intent(tmp_path: Path):
    path = tmp_path / "submission_intents.json"
    _write_intents(path)

    class FailingSession:
        def __call__(self):
            raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        migrate_legacy_submission_intents(FailingSession(), path=str(path))
    assert path.exists()
    assert not (tmp_path / "submission_intents.json.migrated").exists()
