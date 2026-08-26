from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock


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


class SubmissionIntentStore:
    """Durable intents for broker submissions whose outcome may be lost."""

    def __init__(self, path: str = "data/submission_intents.json") -> None:
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self._lock = RLock()

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
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if self.path.exists():
            backup_tmp = self.backup_path.with_suffix(self.backup_path.suffix + ".tmp")
            with backup_tmp.open("wb") as handle:
                handle.write(self.path.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            backup_tmp.replace(self.backup_path)
        tmp.replace(self.path)
        try:
            fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass

    def create(self, *, client_order_id: str, route: str, account_id: str | None,
               symbol: str, side: str, quantity: float, request_fingerprint: str) -> SubmissionIntent:
        if not client_order_id.strip() or not route.strip() or not symbol.strip() or not side.strip():
            raise ValueError("submission intent identity is required")
        if quantity <= 0:
            raise ValueError("submission intent quantity must be positive")
        if not request_fingerprint.strip():
            raise ValueError("request fingerprint is required")
        with self._lock:
            data = self._load_unlocked()
            existing = data.get(client_order_id)
            if existing is not None and existing.get("resolved_at") is None:
                raise RuntimeError("unresolved submission intent already exists")
            intent = SubmissionIntent(
                client_order_id=client_order_id,
                route=route,
                account_id=account_id,
                symbol=symbol.upper(),
                side=side.upper(),
                quantity=float(quantity),
                request_fingerprint=request_fingerprint,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            data[client_order_id] = asdict(intent)
            self._save_unlocked(data)
            return intent

    def resolve(self, client_order_id: str) -> None:
        with self._lock:
            data = self._load_unlocked()
            if client_order_id not in data:
                raise KeyError(client_order_id)
            data[client_order_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()
            self._save_unlocked(data)

    def unresolved(self) -> list[SubmissionIntent]:
        with self._lock:
            data = self._load_unlocked()
            return [SubmissionIntent(**value) for value in data.values() if value.get("resolved_at") is None]

    def unresolved_count(self) -> int:
        return len(self.unresolved())
