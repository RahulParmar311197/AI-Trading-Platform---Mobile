from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from threading import RLock
from uuid import uuid4

from app.execution_lifecycle import OrderStatus


@dataclass(frozen=True)
class ExecutionSnapshot:
    positions: dict[tuple[int, str, str], float]
    open_order_ids: frozenset[str]


class TransactionalExecutionRepository:
    """Single durable transaction boundary for account-scoped execution state."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._db = sqlite3.connect(database_path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS orders("
            "order_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,side TEXT NOT NULL,"
            "quantity REAL NOT NULL,filled_quantity REAL NOT NULL DEFAULT 0,"
            "status TEXT NOT NULL,broker_account_id INTEGER NOT NULL,"
            "broker_route TEXT NOT NULL)"
        )
        order_columns = {row[1] for row in self._db.execute("PRAGMA table_info(orders)")}
        if "broker_account_id" not in order_columns or "broker_route" not in order_columns:
            raise RuntimeError("legacy orders table lacks broker-account identity; migrate before live execution")

        position_columns = {row[1] for row in self._db.execute("PRAGMA table_info(positions)")}
        if not position_columns:
            self._db.execute(
                "CREATE TABLE positions("
                "broker_account_id INTEGER NOT NULL,broker_route TEXT NOT NULL,"
                "symbol TEXT NOT NULL,quantity REAL NOT NULL,"
                "PRIMARY KEY(broker_account_id,broker_route,symbol))"
            )
        elif not {"broker_account_id", "broker_route", "symbol", "quantity"}.issubset(position_columns):
            legacy_count = self._db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
            if legacy_count:
                raise RuntimeError("legacy symbol-only positions cannot be safely attributed to a broker account")
            self._db.execute("DROP TABLE positions")
            self._db.execute(
                "CREATE TABLE positions("
                "broker_account_id INTEGER NOT NULL,broker_route TEXT NOT NULL,"
                "symbol TEXT NOT NULL,quantity REAL NOT NULL,"
                "PRIMARY KEY(broker_account_id,broker_route,symbol))"
            )

        self._db.execute(
            "CREATE TABLE IF NOT EXISTS execution_events("
            "event_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,event_kind TEXT NOT NULL,payload TEXT NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS execution_outbox("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,"
            "event_type TEXT NOT NULL,payload TEXT NOT NULL,published INTEGER NOT NULL DEFAULT 0)"
        )
        self._db.commit()

    def create_order(self, symbol: str, side: str, quantity: float, *, broker_account_id: int, broker_route: str) -> str:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if broker_account_id <= 0:
            raise ValueError("broker_account_id must be positive")
        if not broker_route:
            raise ValueError("broker_route is required")
        order_id = str(uuid4())
        with self._lock:
            self._db.execute(
                "INSERT INTO orders(order_id,symbol,side,quantity,status,broker_account_id,broker_route) VALUES(?,?,?,?,?,?,?)",
                (order_id, symbol.upper(), side.upper(), quantity, OrderStatus.CREATED.value, broker_account_id, broker_route),
            )
            self._db.commit()
        return order_id

    def apply_event(
        self,
        event_id: str,
        order_id: str,
        kind: str,
        *,
        broker_account_id: int,
        broker_route: str,
        price: float | None = None,
        quantity: float = 0.0,
    ) -> bool:
        if not event_id or not order_id:
            raise ValueError("event_id and order_id are required")
        if broker_account_id <= 0 or not broker_route:
            raise ValueError("broker account identity is required")
        with self._lock:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                if self._db.execute("SELECT 1 FROM execution_events WHERE event_id=?", (event_id,)).fetchone():
                    self._db.rollback()
                    return False
                row = self._db.execute(
                    "SELECT symbol,side,quantity,filled_quantity,status,broker_account_id,broker_route FROM orders WHERE order_id=?",
                    (order_id,),
                ).fetchone()
                if row is None:
                    raise KeyError(order_id)
                symbol, side, total, filled, current, stored_account_id, stored_route = row
                if stored_account_id != broker_account_id or stored_route != broker_route:
                    raise ValueError("broker account identity mismatch")
                normalized = kind.upper()
                if normalized in {"PARTIAL_FILL", "FILLED", "FILL"}:
                    if quantity <= 0:
                        raise ValueError("fill quantity must be positive")
                    new_filled = filled + quantity
                    if new_filled > total:
                        raise ValueError("fill exceeds order quantity")
                    status = OrderStatus.FILLED.value if new_filled == total else OrderStatus.PARTIALLY_FILLED.value
                    self._db.execute("UPDATE orders SET filled_quantity=?,status=? WHERE order_id=?", (new_filled, status, order_id))
                    delta = quantity if side == "BUY" else -quantity
                    self._db.execute(
                        "INSERT INTO positions(broker_account_id,broker_route,symbol,quantity) VALUES(?,?,?,?) "
                        "ON CONFLICT(broker_account_id,broker_route,symbol) DO UPDATE SET quantity=quantity+excluded.quantity",
                        (broker_account_id, broker_route, symbol, delta),
                    )
                elif normalized == "SUBMITTED":
                    self._db.execute("UPDATE orders SET status=? WHERE order_id=?", (OrderStatus.SUBMITTED.value, order_id))
                elif normalized in {"CANCELLED", "REJECTED"}:
                    status = OrderStatus.CANCELLED.value if normalized == "CANCELLED" else OrderStatus.REJECTED.value
                    self._db.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))
                else:
                    raise ValueError(f"unsupported execution event: {kind}")
                payload = json.dumps(
                    {"broker_account_id": broker_account_id, "broker_route": broker_route, "price": price, "quantity": quantity, "kind": normalized},
                    sort_keys=True,
                )
                self._db.execute("INSERT INTO execution_events(event_id,order_id,event_kind,payload) VALUES(?,?,?,?)", (event_id, order_id, normalized, payload))
                self._db.execute("INSERT INTO execution_outbox(event_id,event_type,payload) VALUES(?,?,?)", (event_id, normalized, payload))
                self._db.commit()
                return True
            except Exception:
                self._db.rollback()
                raise

    def snapshot(self) -> ExecutionSnapshot:
        with self._lock:
            positions = {
                (int(r[0]), r[1], r[2]): float(r[3])
                for r in self._db.execute("SELECT broker_account_id,broker_route,symbol,quantity FROM positions")
            }
            orders = frozenset(r[0] for r in self._db.execute("SELECT order_id FROM orders WHERE status IN ('SUBMITTED','PARTIALLY_FILLED')"))
            return ExecutionSnapshot(positions, orders)

    def pending_outbox(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id,event_id,event_type,payload FROM execution_outbox WHERE published=0 ORDER BY id LIMIT ?", (limit,)).fetchall()
            return [dict(id=r[0], event_id=r[1], event_type=r[2], payload=json.loads(r[3])) for r in rows]

    def mark_published(self, outbox_id: int) -> None:
        with self._lock:
            self._db.execute("UPDATE execution_outbox SET published=1 WHERE id=?", (outbox_id,))
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()
