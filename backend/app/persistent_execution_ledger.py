from __future__ import annotations

import sqlite3
from threading import RLock
from uuid import uuid4

from app.execution_state_store import ExecutionStateStore
from app.execution_lifecycle import OrderStatus


class PersistentExecutionLedger:
    """Durable order/position state with transactional lifecycle mutations."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL, quantity REAL NOT NULL, filled_quantity REAL NOT NULL DEFAULT 0, status TEXT NOT NULL)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, quantity REAL NOT NULL)")
        self._connection.commit()

    def create(self, *, symbol: str, side: str, quantity: float) -> str:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        order_id = str(uuid4())
        with self._lock:
            self._connection.execute("INSERT INTO orders(order_id,symbol,side,quantity,status) VALUES(?,?,?,?,?)", (order_id, symbol.upper(), side.upper(), quantity, OrderStatus.CREATED.value))
            self._connection.commit()
        return order_id

    def transition(self, order_id: str, status: OrderStatus) -> None:
        with self._lock:
            self._connection.execute("UPDATE orders SET status=? WHERE order_id=?", (status.value, order_id))
            self._connection.commit()

    def fill(self, order_id: str, quantity: float) -> None:
        if quantity <= 0:
            raise ValueError("fill quantity must be positive")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute("SELECT symbol,side,quantity,filled_quantity FROM orders WHERE order_id=?", (order_id,)).fetchone()
                if row is None:
                    raise KeyError(order_id)
                symbol, side, total, filled = row
                new_filled = filled + quantity
                if new_filled > total:
                    raise ValueError("fill exceeds order quantity")
                status = OrderStatus.FILLED.value if new_filled == total else OrderStatus.PARTIALLY_FILLED.value
                self._connection.execute("UPDATE orders SET filled_quantity=?,status=? WHERE order_id=?", (new_filled, status, order_id))
                delta = quantity if side == "BUY" else -quantity
                self._connection.execute("INSERT INTO positions(symbol,quantity) VALUES(?,?) ON CONFLICT(symbol) DO UPDATE SET quantity=quantity+excluded.quantity", (symbol, delta))
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def snapshot(self) -> tuple[dict[str, float], frozenset[str]]:
        with self._lock:
            positions = {r[0]: float(r[1]) for r in self._connection.execute("SELECT symbol,quantity FROM positions").fetchall()}
            orders = frozenset(r[0] for r in self._connection.execute("SELECT order_id FROM orders WHERE status IN ('SUBMITTED','PARTIALLY_FILLED')").fetchall())
            return positions, orders

    def close(self) -> None:
        with self._lock:
            self._connection.close()
