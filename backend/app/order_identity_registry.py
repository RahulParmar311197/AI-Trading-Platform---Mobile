from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class OrderIdentity:
    client_order_id: str
    broker: str
    broker_order_id: str
    broker_account_id: int | None = None
    broker_route: str | None = None


class OrderIdentityRegistry:
    """Durable mapping between internal and broker order identities, scoped by account when known."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._db = sqlite3.connect(database_path, check_same_thread=False)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._db.execute("CREATE TABLE IF NOT EXISTS order_identity(client_order_id TEXT PRIMARY KEY, broker TEXT NOT NULL, broker_order_id TEXT NOT NULL UNIQUE, broker_account_id INTEGER, broker_route TEXT)")
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(order_identity)")}
        if "broker_account_id" not in columns:
            self._db.execute("ALTER TABLE order_identity ADD COLUMN broker_account_id INTEGER")
        if "broker_route" not in columns:
            self._db.execute("ALTER TABLE order_identity ADD COLUMN broker_route TEXT")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_order_identity_account ON order_identity(broker_account_id, broker_route, client_order_id)")
        self._db.commit()

    @staticmethod
    def _validate_scope(identity: OrderIdentity) -> None:
        if identity.broker_account_id is not None and identity.broker_account_id <= 0:
            raise ValueError("broker_account_id must be positive")
        if identity.broker_account_id is not None and not identity.broker_route:
            raise ValueError("broker_route is required with broker_account_id")
        if identity.broker_route and identity.broker_account_id is None:
            raise ValueError("broker_account_id is required with broker_route")

    def bind(self, identity: OrderIdentity) -> None:
        if not identity.client_order_id or not identity.broker or not identity.broker_order_id:
            raise ValueError("client_order_id, broker and broker_order_id are required")
        self._validate_scope(identity)
        with self._lock:
            existing = self._db.execute("SELECT broker,broker_order_id,broker_account_id,broker_route FROM order_identity WHERE client_order_id=?", (identity.client_order_id,)).fetchone()
            if existing and existing != (identity.broker, identity.broker_order_id, identity.broker_account_id, identity.broker_route):
                raise ValueError("client order is already bound to a different broker identity")
            existing_broker = self._db.execute("SELECT client_order_id,broker_account_id,broker_route FROM order_identity WHERE broker=? AND broker_order_id=?", (identity.broker, identity.broker_order_id)).fetchone()
            if existing_broker and existing_broker != (identity.client_order_id, identity.broker_account_id, identity.broker_route):
                raise ValueError("broker order is already bound to a different client identity")
            self._db.execute("INSERT OR IGNORE INTO order_identity(client_order_id,broker,broker_order_id,broker_account_id,broker_route) VALUES(?,?,?,?,?)", (identity.client_order_id, identity.broker, identity.broker_order_id, identity.broker_account_id, identity.broker_route))
            self._db.commit()

    def by_client(self, client_order_id: str, *, broker_account_id: int | None = None, broker_route: str | None = None) -> OrderIdentity | None:
        with self._lock:
            row = self._db.execute("SELECT client_order_id,broker,broker_order_id,broker_account_id,broker_route FROM order_identity WHERE client_order_id=?", (client_order_id,)).fetchone()
        if not row:
            return None
        identity = OrderIdentity(*row)
        if broker_account_id is not None and (identity.broker_account_id != broker_account_id or identity.broker_route != broker_route):
            return None
        return identity

    def by_broker(self, broker: str, broker_order_id: str, *, broker_account_id: int | None = None, broker_route: str | None = None) -> OrderIdentity | None:
        with self._lock:
            row = self._db.execute("SELECT client_order_id,broker,broker_order_id,broker_account_id,broker_route FROM order_identity WHERE broker=? AND broker_order_id=?", (broker, broker_order_id)).fetchone()
        if not row:
            return None
        identity = OrderIdentity(*row)
        if broker_account_id is not None and (identity.broker_account_id != broker_account_id or identity.broker_route != broker_route):
            return None
        return identity

    def close(self) -> None:
        with self._lock:
            self._db.close()
