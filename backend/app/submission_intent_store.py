from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
from typing import Callable, Iterator

from sqlalchemy.exc import IntegrityError

from app.models.submission_intent import SubmissionIntentRecord

try:
    import fcntl
except ImportError:  # pragma: no cover - production deployments are Linux containers
    fcntl = None


@dataclass(frozen=True)
class SubmissionIntent:
    client_order_id: str
    route: str
    account_id: str | None
    symbol: str
    side: str
    quantity: float
    request_fingerprint: str
    created_at: str
    resolved_at: str | None = None
    broker_order_id: str | None = None
    broker_status: str | None = None
    recovered_at: str | None = None


class SubmissionIntentStore:
    """Durable broker submission intents with a database-backed production path."""

    def __init__(self, path: str = "data/submission_intents.json", *, session_factory: Callable[[], object] | None = None) -> None:
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._lock = RLock()
        self._session_factory = session_factory

    @property
    def database_backed(self) -> bool:
        return self._session_factory is not None

    @contextmanager
    def _process_lock(self, *, exclusive: bool) -> Iterator[None]:
        if fcntl is None:
            raise RuntimeError("submission intent file store requires POSIX file locking")
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _to_intent(record: SubmissionIntentRecord) -> SubmissionIntent:
        return SubmissionIntent(
            client_order_id=record.client_order_id,
            route=record.route,
            account_id=record.account_id,
            symbol=record.symbol,
            side=record.side,
            quantity=float(record.quantity),
            request_fingerprint=record.request_fingerprint,
            created_at=record.created_at.isoformat(),
            resolved_at=record.resolved_at.isoformat() if record.resolved_at is not None else None,
            broker_order_id=record.broker_order_id,
            broker_status=record.broker_status,
            recovered_at=record.recovered_at.isoformat() if record.recovered_at is not None else None,
        )

    @staticmethod
    def _validate_replay(existing: SubmissionIntent, request_fingerprint: str) -> SubmissionIntent:
        if existing.request_fingerprint != request_fingerprint:
            raise RuntimeError("submission intent fingerprint mismatch")
        return existing

    def _create_database(self, *, client_order_id: str, route: str, account_id: str | None, symbol: str, side: str, quantity: float, request_fingerprint: str) -> SubmissionIntent:
        assert self._session_factory is not None
        created_at = datetime.now(timezone.utc)
        session = self._session_factory()
        try:
            try:
                with session.begin():
                    existing = session.get(SubmissionIntentRecord, client_order_id)
                    if existing is not None:
                        if existing.resolved_at is None:
                            return self._validate_replay(self._to_intent(existing), request_fingerprint)
                        raise RuntimeError("submission client_order_id has already been resolved and cannot be reused")
                    record = SubmissionIntentRecord(
                        client_order_id=client_order_id, route=route, account_id=account_id,
                        symbol=symbol.upper(), side=side.upper(), quantity=quantity,
                        request_fingerprint=request_fingerprint, created_at=created_at,
                    )
                    session.add(record)
                    session.flush()
                    return self._to_intent(record)
            except IntegrityError:
                session.rollback()
                existing = session.get(SubmissionIntentRecord, client_order_id)
                if existing is None:
                    raise RuntimeError("submission intent creation conflicted with an unavailable record")
                if existing.resolved_at is not None:
                    raise RuntimeError("submission client_order_id has already been resolved and cannot be reused")
                return self._validate_replay(self._to_intent(existing), request_fingerprint)
        finally:
            session.close()

    def _get_database(self, client_order_id: str) -> SubmissionIntent | None:
        assert self._session_factory is not None
        session = self._session_factory()
        try:
            record = session.get(SubmissionIntentRecord, client_order_id)
            if record is None or record.resolved_at is not None:
                return None
            return self._to_intent(record)
        finally:
            session.close()

    def _record_broker_database(self, client_order_id: str, broker_order_id: str, broker_status: str) -> None:
        assert self._session_factory is not None
        broker_order_id = str(broker_order_id).strip()
        if not broker_order_id:
            raise ValueError("broker order id is required")
        session = self._session_factory()
        try:
            with session.begin():
                record = session.get(SubmissionIntentRecord, client_order_id)
                if record is None:
                    raise KeyError(client_order_id)
                if record.broker_order_id is not None and record.broker_order_id != broker_order_id:
                    raise RuntimeError("submission intent is already bound to a different broker order")
                record.broker_order_id = broker_order_id
                record.broker_status = str(broker_status).upper()
                record.recovered_at = datetime.now(timezone.utc)
                session.flush()
        finally:
            session.close()

    def _resolve_database(self, client_order_id: str) -> None:
        assert self._session_factory is not None
        session = self._session_factory()
        try:
            with session.begin():
                record = session.get(SubmissionIntentRecord, client_order_id)
                if record is None:
                    raise KeyError(client_order_id)
                if record.broker_order_id is None:
                    raise RuntimeError("cannot resolve submission intent before broker order is durably bound")
                record.resolved_at = datetime.now(timezone.utc)
                session.flush()
        finally:
            session.close()

    def _unresolved_database(self) -> list[SubmissionIntent]:
        assert self._session_factory is not None
        session = self._session_factory()
        try:
            rows = session.query(SubmissionIntentRecord).filter(SubmissionIntentRecord.resolved_at.is_(None)).all()
            return [self._to_intent(row) for row in rows]
        finally:
            session.close()

    def get_unresolved(self, client_order_id: str) -> SubmissionIntent | None:
        """Return one unresolved intent without treating resolved state as recoverable."""
        client_order_id = str(client_order_id).strip()
        if not client_order_id:
            raise ValueError("client_order_id is required")
        if self._session_factory is not None:
            return self._get_database(client_order_id)
        with self._lock, self._process_lock(exclusive=False):
            data = self._load_unlocked()
            record = data.get(client_order_id)
            if record is None or record.get("resolved_at") is not None:
                return None
            return SubmissionIntent(**record)

    def record_broker_order(self, client_order_id: str, broker_order_id: str, broker_status: str) -> None:
        """Durably bind a submission to the authoritative broker order before resolving it."""
        broker_order_id = str(broker_order_id).strip()
        if not broker_order_id:
            raise ValueError("broker order id is required")
        if self._session_factory is not None:
            self._record_broker_database(client_order_id, broker_order_id, broker_status)
            return
        with self._lock, self._process_lock(exclusive=True):
            data = self._load_unlocked()
            record = data.get(client_order_id)
            if record is None:
                raise KeyError(client_order_id)
            existing = record.get("broker_order_id")
            if existing is not None and existing != broker_order_id:
                raise RuntimeError("submission intent is already bound to a different broker order")
            record["broker_order_id"] = broker_order_id
            record["broker_status"] = str(broker_status).upper()
            record["recovered_at"] = datetime.now(timezone.utc).isoformat()
            self._save_unlocked(data)

    def _load_unlocked(self) -> dict[str, dict]:
        if not self.path.exists():
            if not self.backup_path.exists():
                return {}
            source = self.backup_path
        else:
            source = self.path
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("submission intent state must be an object")
            return data
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            if source == self.path and self.backup_path.exists():
                try:
                    data = json.loads(self.backup_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return data
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    pass
            raise RuntimeError("invalid persisted submission intent state") from exc

    def _save_unlocked(self, data: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("wb") as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        if self.path.exists():
            backup_tmp = self.backup_path.with_suffix(self.backup_path.suffix + ".tmp")
            with backup_tmp.open("wb") as handle:
                handle.write(self.path.read_bytes()); handle.flush(); os.fsync(handle.fileno())
            backup_tmp.replace(self.backup_path)
        tmp.replace(self.path)

    def create(self, *, client_order_id: str, route: str, account_id: str | None, symbol: str, side: str, quantity: float, request_fingerprint: str) -> SubmissionIntent:
        if not client_order_id.strip() or not route.strip() or not symbol.strip() or not side.strip():
            raise ValueError("submission intent identity is required")
        if quantity <= 0:
            raise ValueError("submission intent quantity must be positive")
        if not request_fingerprint.strip():
            raise ValueError("request fingerprint is required")
        if self._session_factory is not None:
            return self._create_database(client_order_id=client_order_id, route=route, account_id=account_id, symbol=symbol, side=side, quantity=quantity, request_fingerprint=request_fingerprint)
        with self._lock, self._process_lock(exclusive=True):
            data = self._load_unlocked()
            existing = data.get(client_order_id)
            if existing is not None:
                if existing.get("resolved_at") is None:
                    return self._validate_replay(SubmissionIntent(**existing), request_fingerprint)
                raise RuntimeError("submission client_order_id has already been resolved and cannot be reused")
            intent = SubmissionIntent(client_order_id=client_order_id, route=route, account_id=account_id, symbol=symbol.upper(), side=side.upper(), quantity=float(quantity), request_fingerprint=request_fingerprint, created_at=datetime.now(timezone.utc).isoformat())
            data[client_order_id] = asdict(intent); self._save_unlocked(data); return intent

    def resolve(self, client_order_id: str) -> None:
        if self._session_factory is not None:
            self._resolve_database(client_order_id); return
        with self._lock, self._process_lock(exclusive=True):
            data = self._load_unlocked(); record = data.get(client_order_id)
            if record is None: raise KeyError(client_order_id)
            if record.get("broker_order_id") is None: raise RuntimeError("cannot resolve submission intent before broker order is durably bound")
            record["resolved_at"] = datetime.now(timezone.utc).isoformat(); self._save_unlocked(data)

    def unresolved(self) -> list[SubmissionIntent]:
        if self._session_factory is not None:
            return self._unresolved_database()
        with self._lock, self._process_lock(exclusive=False):
            data = self._load_unlocked(); return [SubmissionIntent(**value) for value in data.values() if value.get("resolved_at") is None]

    def unresolved_count(self) -> int:
        return len(self.unresolved())
