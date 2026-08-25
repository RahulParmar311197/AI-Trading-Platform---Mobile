from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class OrderIdentity:
    client_order_id: str
    broker: str
    broker_order_id: str


class OrderIdentityRegistry:
    """Durable mapping between internal client order IDs and broker order IDs."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._db = sqlite3.connect(database_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS order_identity(client_order_id TEXT PRIMARY KEY, broker TEXT NOT NULL, broker_order_id TEXT NOT NULL UNIQUE)")
        self._db.commit()

    def bind(self, identity: OrderIdentity) -> None:
        if not identity.client_order_id or not identity.broker or not identity.broker_order_id:
            raise ValueError("client_order_id, broker and broker_order_id are required")
        with self._lock:
            existing = self._db.execute("SELECT broker,broker_order_id FROM order_identity WHERE client_order_id=?", (identity.client_order_id,)).fetchone()
            if existing and existing != (identity.broker, identity.broker_order_id):
                raise ValueError("client order is already bound to a different broker order")
            self._db.execute("INSERT OR IGNORE INTO order_identity(client_order_id,broker,broker_order_id) VALUES(?,?,?)", (identity.client_order_id, identity.broker, identity.broker_order_id))
            self._db.commit()

    def by_client(self, client_order_id: str) -> OrderIdentity | None:
        with self._lock:
            row = self._db.execute("SELECT client_order_id,broker,broker_order_id FROM order_identity WHERE client_order_id=?", (client_order_id,)).fetchone()
        return OrderIdentity(*row) if row else None

    def by_broker(self, broker: str, broker_order_id: str) -> OrderIdentity | None:
        with self._lock:
            row = self._db.execute("SELECT client_order_id,broker,broker_order_id FROM order_identity WHERE broker=? AND broker_order_id=?", (broker, broker_order_id)).fetchone()
        return OrderIdentity(*row) if row else None

    def close(self) -> None:
        with self._lock:
            self._db.close()
