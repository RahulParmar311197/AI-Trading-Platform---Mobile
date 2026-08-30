from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import os
import shutil

from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from app.models.submission_intent import SubmissionIntentRecord
from app.submission_intent_store import SubmissionIntentStore


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_startup_migrations() -> None:
    """Upgrade the application database to the Alembic head before trading startup."""
    alembic_ini = BACKEND_ROOT / "alembic.ini"
    alembic_dir = BACKEND_ROOT / "alembic"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(alembic_dir))
    command.upgrade(config, "head")


def _archive_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".migrated")
    if not candidate.exists():
        return candidate
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return path.with_name(path.name + f".migrated.{stamp}")


def _archive_legacy_file(path: Path) -> Path:
    archive = _archive_path(path)
    path.replace(archive)
    return archive


def migrate_legacy_submission_intents(
    session_factory: Callable[[], object],
    *,
    path: str = "data/submission_intents.json",
) -> int:
    """Import unresolved JSON intents into the database before live execution starts.

    The legacy file is locked for the entire read/DB-commit/archive sequence. Existing
    database rows are accepted only when they exactly match the legacy intent and remain
    unresolved. Any conflict fails closed; the legacy file is never moved before commit.
    """
    store = SubmissionIntentStore(path)
    legacy_path = store.path
    backup_path = store.backup_path
    if not legacy_path.exists() and not backup_path.exists():
        return 0

    with store._lock, store._process_lock(exclusive=True):
        try:
            raw = store._load_unlocked()
        except RuntimeError:
            raise

        intents = []
        for client_order_id, value in raw.items():
            if not isinstance(value, dict):
                raise RuntimeError(f"invalid legacy submission intent: {client_order_id}")
            try:
                if value.get("resolved_at") is not None:
                    continue
                intent = store.create
                required = (
                    "route", "symbol", "side", "quantity", "request_fingerprint", "created_at"
                )
                if not all(key in value for key in required):
                    raise RuntimeError(f"incomplete legacy submission intent: {client_order_id}")
                intents.append((client_order_id, value))
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"invalid legacy submission intent: {client_order_id}") from exc

        session = session_factory()
        try:
            with session.begin():
                for client_order_id, value in intents:
                    existing = session.get(SubmissionIntentRecord, client_order_id)
                    if existing is None:
                        session.add(
                            SubmissionIntentRecord(
                                client_order_id=client_order_id,
                                route=str(value["route"]),
                                account_id=(
                                    None if value.get("account_id") is None
                                    else str(value["account_id"])
                                ),
                                symbol=str(value["symbol"]).strip().upper(),
                                side=str(value["side"]).strip().upper(),
                                quantity=float(value["quantity"]),
                                request_fingerprint=str(value["request_fingerprint"]),
                                created_at=datetime.fromisoformat(str(value["created_at"])),
                                resolved_at=None,
                            )
                        )
                        continue

                    legacy_tuple = (
                        str(value["route"]),
                        None if value.get("account_id") is None else str(value["account_id"]),
                        str(value["symbol"]).strip().upper(),
                        str(value["side"]).strip().upper(),
                        float(value["quantity"]),
                        str(value["request_fingerprint"]),
                    )
                    db_tuple = (
                        existing.route,
                        existing.account_id,
                        existing.symbol,
                        existing.side,
                        float(existing.quantity),
                        existing.request_fingerprint,
                    )
                    if existing.resolved_at is not None or db_tuple != legacy_tuple:
                        raise RuntimeError(
                            f"conflicting durable submission intent: {client_order_id}"
                        )

                try:
                    session.flush()
                except IntegrityError as exc:
                    raise RuntimeError("legacy submission intent migration conflict") from exc
        finally:
            session.close()

        archived = []
        if legacy_path.exists():
            archived.append(_archive_legacy_file(legacy_path))
        if backup_path.exists():
            archived.append(_archive_legacy_file(backup_path))
        if archived:
            try:
                fd = os.open(legacy_path.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError:
                pass
        return len(intents)
