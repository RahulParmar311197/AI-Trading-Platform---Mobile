from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.order_lifecycle import OrderLifecycle, OrderStatus, PositionStatus


class ExecutionStateStore:
    """Atomic JSON execution-state store with a last-known-good recovery copy."""

    def __init__(self, path: str = "data/execution_state.json"):
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")

    def _serialize(self, lifecycle: OrderLifecycle) -> dict:
        payload = {"orders": {}, "positions": {}}
        for oid, order in lifecycle.orders.items():
            payload["orders"][oid] = {
                **asdict(order),
                "status": order.status.value,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
            }
        for symbol, position in lifecycle.positions.items():
            payload["positions"][symbol] = {**asdict(position), "status": position.status.value}
        return payload

    def _write_atomic(self, target: Path, payload: dict) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        data = json.dumps(payload, indent=2, sort_keys=True)
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(target)
        try:
            directory_fd = os.open(str(target.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Some platforms/filesystems do not allow directory fsync; the
            # atomic replace is still the primary integrity guarantee.
            pass

    def save(self, lifecycle: OrderLifecycle) -> None:
        payload = self._serialize(lifecycle)
        if self.path.exists():
            # Preserve the previous complete snapshot before replacing the
            # live file, so a torn/corrupt latest file remains recoverable.
            backup_tmp = self.backup_path.with_suffix(self.backup_path.suffix + ".tmp")
            backup_tmp.write_bytes(self.path.read_bytes())
            with backup_tmp.open("rb") as handle:
                os.fsync(handle.fileno())
            backup_tmp.replace(self.backup_path)
        self._write_atomic(self.path, payload)

    def _deserialize_into(self, lifecycle: OrderLifecycle, data: dict) -> None:
        lifecycle.orders.clear()
        lifecycle.positions.clear()
        from app.order_lifecycle import OrderRecord, PositionRecord

        for oid, raw in data.get("orders", {}).items():
            value = dict(raw)
            value["status"] = OrderStatus(value["status"])
            value["created_at"] = datetime.fromisoformat(value["created_at"])
            value["updated_at"] = datetime.fromisoformat(value["updated_at"])
            lifecycle.orders[oid] = OrderRecord(**value)

        for symbol, raw in data.get("positions", {}).items():
            value = dict(raw)
            value["status"] = PositionStatus(value["status"])
            lifecycle.positions[symbol] = PositionRecord(**value)

    def load(self, lifecycle: OrderLifecycle) -> bool:
        candidates = [self.path, self.backup_path]
        if not any(candidate.exists() for candidate in candidates):
            return False

        last_error: Exception | None = None
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                self._deserialize_into(lifecycle, data)
                if candidate == self.backup_path:
                    # Restore the last-known-good snapshot as the active file.
                    self._write_atomic(self.path, data)
                return True
            except (OSError, ValueError, TypeError, KeyError) as exc:
                last_error = exc

        raise RuntimeError("execution state is unreadable") from last_error
