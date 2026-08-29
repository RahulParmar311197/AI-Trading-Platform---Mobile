from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from threading import RLock
from uuid import uuid4

from app.execution_lifecycle import OrderStatus


@dataclass(frozen=True)
class ExecutionSnapshot:
    positions: dict[tuple[int, str, str], float]
    open_order_ids: frozenset[str]


@dataclass(frozen=True)
class OrderIdentity:
    client_order_id: str
    broker: str
    broker_order_id: str
    broker_account_id: int | None = None
    broker_route: str | None = None


@dataclass(frozen=True)
class SubmissionRecord:
    idempotency_key: str
    client_order_id: str
    broker_account_id: int
    broker_route: str
    status: str
    broker_order_id: str | None


class TransactionalExecutionRepository:
    """Single durable transaction boundary for account-scoped execution state and identities."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._db = sqlite3.connect(database_path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._db.execute("CREATE TABLE IF NOT EXISTS orders(order_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,side TEXT NOT NULL,quantity REAL NOT NULL,filled_quantity REAL NOT NULL DEFAULT 0,status TEXT NOT NULL,broker_account_id INTEGER NOT NULL,broker_route TEXT NOT NULL)")
        columns={row[1] for row in self._db.execute("PRAGMA table_info(orders)")}
        if "broker_account_id" not in columns or "broker_route" not in columns: raise RuntimeError("legacy orders table lacks broker-account identity; migrate before live execution")
        pcols={row[1] for row in self._db.execute("PRAGMA table_info(positions)")}
        if not pcols: self._db.execute("CREATE TABLE positions(broker_account_id INTEGER NOT NULL,broker_route TEXT NOT NULL,symbol TEXT NOT NULL,quantity REAL NOT NULL,PRIMARY KEY(broker_account_id,broker_route,symbol))")
        elif not {"broker_account_id","broker_route","symbol","quantity"}.issubset(pcols):
            if self._db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]: raise RuntimeError("legacy symbol-only positions cannot be safely attributed to a broker account")
            self._db.execute("DROP TABLE positions"); self._db.execute("CREATE TABLE positions(broker_account_id INTEGER NOT NULL,broker_route TEXT NOT NULL,symbol TEXT NOT NULL,quantity REAL NOT NULL,PRIMARY KEY(broker_account_id,broker_route,symbol))")
        self._db.execute("CREATE TABLE IF NOT EXISTS execution_events(event_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,event_kind TEXT NOT NULL,payload TEXT NOT NULL)")
        self._db.execute("CREATE TABLE IF NOT EXISTS execution_outbox(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,event_type TEXT NOT NULL,payload TEXT NOT NULL,published INTEGER NOT NULL DEFAULT 0,claim_token TEXT,claim_expires_at REAL)")
        outbox_cols={row[1] for row in self._db.execute("PRAGMA table_info(execution_outbox)")}
        if "claim_token" not in outbox_cols: self._db.execute("ALTER TABLE execution_outbox ADD COLUMN claim_token TEXT")
        if "claim_expires_at" not in outbox_cols: self._db.execute("ALTER TABLE execution_outbox ADD COLUMN claim_expires_at REAL")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_execution_outbox_pending ON execution_outbox(published,claim_expires_at,id)")
        self._db.execute("CREATE TABLE IF NOT EXISTS order_identity(client_order_id TEXT PRIMARY KEY,broker TEXT NOT NULL,broker_order_id TEXT NOT NULL,broker_account_id INTEGER NOT NULL,broker_route TEXT NOT NULL,UNIQUE(broker,broker_order_id,broker_account_id,broker_route))")
        identity_cols={row[1] for row in self._db.execute("PRAGMA table_info(order_identity)")}
        if not {"broker_account_id","broker_route"}.issubset(identity_cols):
            count=self._db.execute("SELECT COUNT(*) FROM order_identity").fetchone()[0]
            if count: raise RuntimeError("legacy identity rows lack broker-account scope; migrate before live execution")
            self._db.execute("DROP TABLE order_identity")
            self._db.execute("CREATE TABLE order_identity(client_order_id TEXT PRIMARY KEY,broker TEXT NOT NULL,broker_order_id TEXT NOT NULL,broker_account_id INTEGER NOT NULL,broker_route TEXT NOT NULL,UNIQUE(broker,broker_order_id,broker_account_id,broker_route))")
        self._db.execute("CREATE TABLE IF NOT EXISTS order_submissions(idempotency_key TEXT PRIMARY KEY,client_order_id TEXT NOT NULL,broker_account_id INTEGER NOT NULL,broker_route TEXT NOT NULL,status TEXT NOT NULL,broker_order_id TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_order_submissions_status ON order_submissions(status,updated_at)")
        self._db.commit()

    def create_order(self,symbol:str,side:str,quantity:float,*,broker_account_id:int,broker_route:str)->str:
        if quantity<=0 or broker_account_id<=0 or not broker_route: raise ValueError("positive quantity, broker account identity and broker route are required")
        order_id=str(uuid4())
        with self._lock:
            self._db.execute("INSERT INTO orders(order_id,symbol,side,quantity,status,broker_account_id,broker_route) VALUES(?,?,?,?,?,?,?)",(order_id,symbol.upper(),side.upper(),quantity,OrderStatus.CREATED.value,broker_account_id,broker_route)); self._db.commit()
        return order_id

    def get_order(self, order_id: str) -> dict | None:
        """Return the durable order projection used by submission/recovery boundaries."""
        if not order_id:
            return None
        with self._lock:
            row=self._db.execute("SELECT order_id,symbol,side,quantity,filled_quantity,status,broker_account_id,broker_route FROM orders WHERE order_id=?",(order_id,)).fetchone()
        if row is None:
            return None
        return {"order_id":row[0],"symbol":row[1],"side":row[2],"quantity":float(row[3]),"filled_quantity":float(row[4]),"status":row[5],"broker_account_id":int(row[6]),"broker_route":row[7]}

    def register_submission(self,idempotency_key:str,client_order_id:str,broker_account_id:int,broker_route:str)->SubmissionRecord:
        if not idempotency_key or not client_order_id or broker_account_id<=0 or not broker_route: raise ValueError("submission identity is required")
        now=time.time()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute("INSERT OR IGNORE INTO order_submissions(idempotency_key,client_order_id,broker_account_id,broker_route,status,broker_order_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(idempotency_key,client_order_id,broker_account_id,broker_route,"PENDING",None,now,now))
                row=self._db.execute("SELECT idempotency_key,client_order_id,broker_account_id,broker_route,status,broker_order_id FROM order_submissions WHERE idempotency_key=?",(idempotency_key,)).fetchone()
                if row[1:]!=(client_order_id,broker_account_id,broker_route,row[4],row[5]):
                    raise ValueError("idempotency key is bound to a different order scope")
                self._db.commit()
                return SubmissionRecord(*row)
            except Exception:
                self._db.rollback(); raise

    def mark_submission_submitted(self,idempotency_key:str,broker_order_id:str)->SubmissionRecord:
        if not idempotency_key or not broker_order_id: raise ValueError("submission identifiers are required")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                updated=self._db.execute("UPDATE order_submissions SET status='SUBMITTED',broker_order_id=?,updated_at=? WHERE idempotency_key=? AND status='PENDING'",(broker_order_id,time.time(),idempotency_key)).rowcount
                if updated!=1:
                    row=self._db.execute("SELECT idempotency_key,client_order_id,broker_account_id,broker_route,status,broker_order_id FROM order_submissions WHERE idempotency_key=?",(idempotency_key,)).fetchone()
                    if not row: raise KeyError(idempotency_key)
                    if row[5]!=broker_order_id: raise ValueError("submission is already bound to a different broker order")
                row=self._db.execute("SELECT idempotency_key,client_order_id,broker_account_id,broker_route,status,broker_order_id FROM order_submissions WHERE idempotency_key=?",(idempotency_key,)).fetchone()
                self._db.commit(); return SubmissionRecord(*row)
            except Exception:
                self._db.rollback(); raise

    def get_submission(self,idempotency_key:str)->SubmissionRecord|None:
        with self._lock:
            row=self._db.execute("SELECT idempotency_key,client_order_id,broker_account_id,broker_route,status,broker_order_id FROM order_submissions WHERE idempotency_key=?",(idempotency_key,)).fetchone()
        return SubmissionRecord(*row) if row else None

    def pending_submissions(self,limit:int=100)->list[SubmissionRecord]:
        with self._lock:
            rows=self._db.execute("SELECT idempotency_key,client_order_id,broker_account_id,broker_route,status,broker_order_id FROM order_submissions WHERE status='PENDING' ORDER BY created_at LIMIT ?",(limit,)).fetchall()
        return [SubmissionRecord(*row) for row in rows]

    def bind_identity(self,identity:OrderIdentity)->None:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._bind_identity_tx(identity); self._db.commit()
            except Exception: self._db.rollback(); raise

    def bind_broker_identity(self, client_order_id: str, broker: str, broker_order_id: str, *, broker_account_id: int, broker_route: str) -> None:
        """Compatibility facade for callers that provide the identity fields separately."""
        self.bind_identity(OrderIdentity(client_order_id, broker, broker_order_id, broker_account_id, broker_route))

    def _bind_identity_tx(self,identity:OrderIdentity)->None:
        if not identity.client_order_id or not identity.broker or not identity.broker_order_id: raise ValueError("client_order_id, broker and broker_order_id are required")
        if identity.broker_account_id is None or identity.broker_account_id<=0 or not identity.broker_route: raise ValueError("broker account identity and route are required")
        order=self._db.execute("SELECT broker_account_id,broker_route FROM orders WHERE order_id=?",(identity.client_order_id,)).fetchone()
        if order is None: raise KeyError(identity.client_order_id)
        if order!=(identity.broker_account_id,identity.broker_route): raise ValueError("client order broker account identity mismatch")
        row=self._db.execute("SELECT broker,broker_order_id,broker_account_id,broker_route FROM order_identity WHERE client_order_id=?",(identity.client_order_id,)).fetchone()
        if row and row!=(identity.broker,identity.broker_order_id,identity.broker_account_id,identity.broker_route): raise ValueError("client order is already bound to a different broker identity")
        reverse=self._db.execute("SELECT client_order_id FROM order_identity WHERE broker=? AND broker_order_id=? AND broker_account_id=? AND broker_route=?",(identity.broker,identity.broker_order_id,identity.broker_account_id,identity.broker_route)).fetchone()
        if reverse and reverse[0]!=identity.client_order_id: raise ValueError("broker order is already bound to a different client order")
        self._db.execute("INSERT OR IGNORE INTO order_identity(client_order_id,broker,broker_order_id,broker_account_id,broker_route) VALUES(?,?,?,?,?)",(identity.client_order_id,identity.broker,identity.broker_order_id,identity.broker_account_id,identity.broker_route))

    def get_identity_by_broker(self,broker:str,broker_order_id:str,*,broker_account_id:int,broker_route:str)->OrderIdentity|None:
        with self._lock:
            row=self._db.execute("SELECT client_order_id,broker,broker_order_id,broker_account_id,broker_route FROM order_identity WHERE broker=? AND broker_order_id=? AND broker_account_id=? AND broker_route=?",(broker,broker_order_id,broker_account_id,broker_route)).fetchone()
        return OrderIdentity(*row) if row else None

    def _apply_event_tx(self,event_id:str,order_id:str,kind:str,*,broker_account_id:int,broker_route:str,price:float|None,quantity:float)->bool:
        if self._db.execute("SELECT 1 FROM execution_events WHERE event_id=?",(event_id,)).fetchone(): return False
        row=self._db.execute("SELECT symbol,side,quantity,filled_quantity,broker_account_id,broker_route FROM orders WHERE order_id=?",(order_id,)).fetchone()
        if row is None: raise KeyError(order_id)
        symbol,side,total,filled,stored_account,stored_route=row
        if stored_account!=broker_account_id or stored_route!=broker_route: raise ValueError("broker account identity mismatch")
        normalized=kind.upper()
        if normalized in {"PARTIAL_FILL","FILLED","FILL"}:
            if quantity<=0 or filled+quantity>total: raise ValueError("invalid fill quantity")
            new_filled=filled+quantity; status=OrderStatus.FILLED.value if new_filled==total else OrderStatus.PARTIALLY_FILLED.value
            self._db.execute("UPDATE orders SET filled_quantity=?,status=? WHERE order_id=?",(new_filled,status,order_id))
            delta=quantity if side=="BUY" else -quantity
            self._db.execute("INSERT INTO positions(broker_account_id,broker_route,symbol,quantity) VALUES(?,?,?,?) ON CONFLICT(broker_account_id,broker_route,symbol) DO UPDATE SET quantity=quantity+excluded.quantity",(broker_account_id,broker_route,symbol,delta))
        elif normalized=="SUBMITTED": self._db.execute("UPDATE orders SET status=? WHERE order_id=?",(OrderStatus.SUBMITTED.value,order_id))
        elif normalized in {"CANCELLED","REJECTED"}: self._db.execute("UPDATE orders SET status=? WHERE order_id=?",(OrderStatus.CANCELLED.value if normalized=="CANCELLED" else OrderStatus.REJECTED.value,order_id))
        else: raise ValueError(f"unsupported execution event: {kind}")
        payload=json.dumps({"broker_account_id":broker_account_id,"broker_route":broker_route,"price":price,"quantity":quantity,"kind":normalized},sort_keys=True)
        self._db.execute("INSERT INTO execution_events(event_id,order_id,event_kind,payload) VALUES(?,?,?,?)",(event_id,order_id,normalized,payload))
        self._db.execute("INSERT INTO execution_outbox(event_id,event_type,payload) VALUES(?,?,?)",(event_id,normalized,payload)); return True

    def apply_event(self,event_id:str,order_id:str,kind:str,*,broker_account_id:int,broker_route:str,price:float|None=None,quantity:float=0.0)->bool:
        if not event_id or not order_id or broker_account_id<=0 or not broker_route: raise ValueError("event and broker account identity are required")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                result=self._apply_event_tx(event_id,order_id,kind,broker_account_id=broker_account_id,broker_route=broker_route,price=price,quantity=quantity); self._db.commit(); return result
            except Exception: self._db.rollback(); raise

    def bind_identity_and_apply_event(self,identity:OrderIdentity,event_id:str,kind:str,*,broker_account_id:int,broker_route:str,price:float|None=None,quantity:float=0.0)->bool:
        if identity.broker_account_id!=broker_account_id or identity.broker_route!=broker_route: raise ValueError("identity scope does not match execution scope")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._bind_identity_tx(identity)
                result=self._apply_event_tx(event_id,identity.client_order_id,kind,broker_account_id=broker_account_id,broker_route=broker_route,price=price,quantity=quantity)
                self._db.commit(); return result
            except Exception: self._db.rollback(); raise

    def snapshot(self)->ExecutionSnapshot:
        with self._lock:
            positions={(int(r[0]),r[1],r[2]):float(r[3]) for r in self._db.execute("SELECT broker_account_id,broker_route,symbol,quantity FROM positions")}
            orders=frozenset(r[0] for r in self._db.execute("SELECT order_id FROM orders WHERE status IN ('SUBMITTED','PARTIALLY_FILLED')")); return ExecutionSnapshot(positions,orders)

    def pending_outbox(self,limit:int=100)->list[dict]:
        now=time.time()
        with self._lock:
            rows=self._db.execute("SELECT id,event_id,event_type,payload FROM execution_outbox WHERE published=0 AND (claim_token IS NULL OR claim_expires_at<=?) ORDER BY id LIMIT ?",(now,limit)).fetchall(); return [dict(id=r[0],event_id=r[1],event_type=r[2],payload=json.loads(r[3])) for r in rows]

    def claim_outbox(self,*,limit:int=100,lease_seconds:float=30.0)->list[dict]:
        if limit<=0 or lease_seconds<=0: raise ValueError("positive limit and lease are required")
        now=time.time(); expires=now+lease_seconds; token=str(uuid4())
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                rows=self._db.execute("SELECT id,event_id,event_type,payload FROM execution_outbox WHERE published=0 AND (claim_token IS NULL OR claim_expires_at<=?) ORDER BY id LIMIT ?",(now,limit)).fetchall()
                for row in rows: self._db.execute("UPDATE execution_outbox SET claim_token=?,claim_expires_at=? WHERE id=? AND published=0 AND (claim_token IS NULL OR claim_expires_at<=?)",(token,expires,row[0],now))
                self._db.commit()
            except Exception:
                self._db.rollback(); raise
        return [dict(id=r[0],event_id=r[1],event_type=r[2],payload=json.loads(r[3]),claim_token=token) for r in rows]

    def mark_published(self,outbox_id:int,claim_token:str)->None:
        if not claim_token: raise ValueError("claim token is required")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                updated=self._db.execute("UPDATE execution_outbox SET published=1,claim_token=NULL,claim_expires_at=NULL WHERE id=? AND published=0 AND claim_token=?",(outbox_id,claim_token)).rowcount
                if updated!=1: raise RuntimeError("outbox publication claim is no longer owned")
                self._db.commit()
            except Exception:
                self._db.rollback(); raise

    def close(self)->None:
        with self._lock: self._db.close()
