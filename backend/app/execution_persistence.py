from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from datetime import datetime

from app.order_lifecycle import OrderLifecycle, OrderStatus, PositionStatus

EXECUTION_STATE_SCHEMA_VERSION = 3


class ExecutionStateStore:
    """Atomic versioned JSON execution-state store with fail-closed recovery."""

    def __init__(self, path: str = "data/execution_state.json"):
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")

    def _serialize(self, lifecycle: OrderLifecycle) -> dict:
        payload = {"schema_version": EXECUTION_STATE_SCHEMA_VERSION, "orders": {}, "positions": {}, "realized_pnl_by_symbol": {}, "realized_pnl_by_day": {}}
        for oid, order in lifecycle.orders.items():
            raw = asdict(order)
            raw["status"] = order.status.value; raw["created_at"] = order.created_at.isoformat(); raw["updated_at"] = order.updated_at.isoformat()
            payload["orders"][oid] = raw
        for symbol, position in lifecycle.positions.items(): payload["positions"][symbol] = {**asdict(position), "status": position.status.value}
        payload["realized_pnl_by_symbol"] = {str(k).upper(): float(v) for k, v in lifecycle.realized_pnl_by_symbol.items()}
        payload["realized_pnl_by_day"] = {str(k): float(v) for k, v in lifecycle.realized_pnl_by_day.items()}
        return payload

    def _write_atomic(self, target: Path, payload: dict) -> None:
        target.parent.mkdir(parents=True, exist_ok=True); tmp = target.with_suffix(target.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True)); handle.flush(); os.fsync(handle.fileno())
        tmp.replace(target)
        try:
            fd = os.open(str(target.parent), os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        except OSError: pass

    def save(self, lifecycle: OrderLifecycle) -> None:
        payload = self._serialize(lifecycle)
        if self.path.exists():
            backup_tmp = self.backup_path.with_suffix(self.backup_path.suffix + ".tmp")
            backup_tmp.write_bytes(self.path.read_bytes())
            with backup_tmp.open("rb") as handle: os.fsync(handle.fileno())
            backup_tmp.replace(self.backup_path)
        self._write_atomic(self.path, payload)

    @staticmethod
    def _migrate(data: dict) -> dict:
        if not isinstance(data, dict): raise ValueError("execution state must be an object")
        version = data.get("schema_version", 1)
        if not isinstance(version, int) or version < 1: raise ValueError("invalid execution state schema version")
        if version > EXECUTION_STATE_SCHEMA_VERSION: raise ValueError(f"unsupported execution state schema version: {version}")
        migrated = dict(data)
        if version == 1:
            migrated["schema_version"] = 2
            for raw in migrated.get("orders", {}).values():
                if not isinstance(raw, dict): raise ValueError("invalid order record")
                raw.setdefault("execution_id", None)
            version = 2
        if version == 2:
            migrated["schema_version"] = 3
            for raw in migrated.get("positions", {}).values():
                if not isinstance(raw, dict): raise ValueError("invalid position record")
                # Legacy positions were not broker-account scoped. Preserve them explicitly
                # as unscoped so multi-account recovery can fail closed rather than guess.
                raw.setdefault("broker_account_id", None)
                raw.setdefault("broker_route", None)
        return migrated

    def _deserialize_into(self, lifecycle: OrderLifecycle, data: dict) -> None:
        data = self._migrate(data)
        lifecycle.orders.clear(); lifecycle.positions.clear(); lifecycle.realized_pnl_by_symbol.clear(); lifecycle.realized_pnl_by_day.clear()
        from app.order_lifecycle import OrderRecord, PositionRecord
        orders = data.get("orders", {}); positions = data.get("positions", {})
        if not isinstance(orders, dict) or not isinstance(positions, dict): raise ValueError("orders and positions must be objects")
        for oid, raw in orders.items():
            if not isinstance(raw, dict): raise ValueError("invalid order record")
            value = dict(raw); value["status"] = OrderStatus(value["status"]); value["created_at"] = datetime.fromisoformat(value["created_at"]); value["updated_at"] = datetime.fromisoformat(value["updated_at"]); value.setdefault("execution_id", None)
            lifecycle.orders[oid] = OrderRecord(**value)
        for symbol, raw in positions.items():
            if not isinstance(raw, dict): raise ValueError("invalid position record")
            value = dict(raw); value["status"] = PositionStatus(value["status"]); value.setdefault("broker_account_id", None); value.setdefault("broker_route", None); lifecycle.positions[symbol] = PositionRecord(**value)
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
        if not any(p.exists() for p in candidates): return False
        last_error = None
        for candidate in candidates:
            if not candidate.exists(): continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8")); migrated = self._migrate(data); self._deserialize_into(lifecycle, migrated)
                if candidate == self.backup_path or data.get("schema_version", 1) != EXECUTION_STATE_SCHEMA_VERSION: self._write_atomic(self.path, migrated)
                return True
            except (OSError, ValueError, TypeError, KeyError) as exc: last_error = exc
        raise RuntimeError("execution state is unreadable") from last_error
