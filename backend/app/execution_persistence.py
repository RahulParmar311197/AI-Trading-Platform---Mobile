from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from datetime import datetime

from app.order_lifecycle import OrderLifecycle, OrderStatus, PositionStatus


class ExecutionStateStore:
    """Atomic JSON execution-state store with last-known-good recovery copy."""

    def __init__(self, path: str = "data/execution_state.json"):
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")

    def _serialize(self, lifecycle: OrderLifecycle) -> dict:
        payload = {"orders": {}, "positions": {}, "realized_pnl_by_symbol": {}, "realized_pnl_by_day": {}}
        for oid, order in lifecycle.orders.items():
            raw = asdict(order)
            raw["status"] = order.status.value
            raw["created_at"] = order.created_at.isoformat()
            raw["updated_at"] = order.updated_at.isoformat()
            payload["orders"][oid] = raw
        for symbol, position in lifecycle.positions.items():
            payload["positions"][symbol] = {**asdict(position), "status": position.status.value}
        payload["realized_pnl_by_symbol"] = {str(symbol).upper(): float(value) for symbol, value in lifecycle.realized_pnl_by_symbol.items()}
        payload["realized_pnl_by_day"] = {str(day): float(value) for day, value in lifecycle.realized_pnl_by_day.items()}
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
            pass

    def save(self, lifecycle: OrderLifecycle) -> None:
        payload = self._serialize(lifecycle)
        if self.path.exists():
            backup_tmp = self.backup_path.with_suffix(self.backup_path.suffix + ".tmp")
            backup_tmp.write_bytes(self.path.read_bytes())
            with backup_tmp.open("rb") as handle:
                os.fsync(handle.fileno())
            backup_tmp.replace(self.backup_path)
        self._write_atomic(self.path, payload)

    def _deserialize_into(self, lifecycle: OrderLifecycle, data: dict) -> None:
        lifecycle.orders.clear(); lifecycle.positions.clear(); lifecycle.realized_pnl_by_symbol.clear(); lifecycle.realized_pnl_by_day.clear()
        from app.order_lifecycle import OrderRecord, PositionRecord
        for oid, raw in data.get("orders", {}).items():
            value = dict(raw); value["status"] = OrderStatus(value["status"]); value["created_at"] = datetime.fromisoformat(value["created_at"]); value["updated_at"] = datetime.fromisoformat(value["updated_at"])
            lifecycle.orders[oid] = OrderRecord(**value)
        for symbol, raw in data.get("positions", {}).items():
            value = dict(raw); value["status"] = PositionStatus(value["status"]); lifecycle.positions[symbol] = PositionRecord(**value)
        raw_pnl = data.get("realized_pnl_by_symbol", {})
        if not isinstance(raw_pnl, dict): raise ValueError("realized_pnl_by_symbol must be an object")
        for symbol, value in raw_pnl.items():
            pnl = float(value)
            if not pnl == pnl or pnl in (float("inf"), float("-inf")): raise ValueError(f"invalid realized pnl for {symbol}")
            lifecycle.realized_pnl_by_symbol[str(symbol).upper()] = pnl
        raw_daily = data.get("realized_pnl_by_day", {})
        if not isinstance(raw_daily, dict): raise ValueError("realized_pnl_by_day must be an object")
        for day, value in raw_daily.items():
            datetime.strptime(str(day), "%Y-%m-%d"); pnl = float(value)
            if not pnl == pnl or pnl in (float("inf"), float("-inf")): raise ValueError(f"invalid realized daily pnl for {day}")
            lifecycle.realized_pnl_by_day[str(day)] = pnl

    def load(self, lifecycle: OrderLifecycle) -> bool:
        candidates = [self.path, self.backup_path]
        if not any(candidate.exists() for candidate in candidates): return False
        last_error: Exception | None = None
        for candidate in candidates:
            if not candidate.exists(): continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8")); self._deserialize_into(lifecycle, data)
                if candidate == self.backup_path: self._write_atomic(self.path, data)
                return True
            except (OSError, ValueError, TypeError, KeyError) as exc: last_error = exc
        raise RuntimeError("execution state is unreadable") from last_error
