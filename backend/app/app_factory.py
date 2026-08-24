from __future__ import annotations

from dataclasses import dataclass
from fastapi import FastAPI
from app.db import init_db
from app.db_runtime import create_db_runtime
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.safety_state import SafetyStateStore
from app.broker_factory import build_broker_router
from app.broker_router import BrokerRouter
from app.execution_authorization import ExecutionAuthorization
from app.startup_execution_state import StartupExecutionStateMachine
from app.trading_audit import TradingAuditLog
from app.emergency_halt import EmergencyHaltController


@dataclass
class AppResources:
    execution_store: ExecutionStateStore
    idempotency_store: IdempotencyStore
    safety_store: SafetyStateStore
    audit_log: TradingAuditLog
    authorization: ExecutionAuthorization | None = None
    session_local: object | None = None
    startup_execution_state: StartupExecutionStateMachine | None = None
    emergency_halt_controller: EmergencyHaltController | None = None


def create_resources(*, execution_path="data/execution_state.json", idempotency_path="data/idempotency.sqlite3", safety_path="data/safety_state.json", audit_path="data/trading_audit.jsonl", database_url: str | None = None) -> AppResources:
    session_local = None
    if database_url:
        _, session_local = create_db_runtime(database_url)
    safety_store = SafetyStateStore(safety_path)
    audit_log = TradingAuditLog(audit_path)
    startup_execution_state = StartupExecutionStateMachine(audit_log)
    emergency_halt_controller = EmergencyHaltController(safety_store, startup_execution_state, audit_log)
    return AppResources(
        execution_store=ExecutionStateStore(execution_path),
        idempotency_store=IdempotencyStore(idempotency_path),
        safety_store=safety_store,
        audit_log=audit_log,
        authorization=ExecutionAuthorization(safety_store),
        session_local=session_local,
        startup_execution_state=startup_execution_state,
        emergency_halt_controller=emergency_halt_controller,
    )


def create_app(resources: AppResources | None = None, broker_router: BrokerRouter | None = None) -> FastAPI:
    resources = resources or create_resources()
    app = FastAPI(title="AI Trading Platform", version="1.0.0")
    app.state.resources = resources
    app.state.broker_router = broker_router or build_broker_router(resources.safety_store)
    app.state.startup_execution_state = resources.startup_execution_state
    app.state.emergency_halt_controller = resources.emergency_halt_controller
    app.state.trading_audit_log = resources.audit_log

    @app.on_event("startup")
    async def startup() -> None:
        if resources.session_local is None:
            init_db()

    from app.api.orders import router as orders_router
    from app.api.ensemble import router as decision_router
    app.include_router(orders_router)
    app.include_router(decision_router)
    return app
