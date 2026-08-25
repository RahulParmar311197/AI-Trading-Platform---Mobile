from __future__ import annotations

from dataclasses import dataclass
from fastapi import FastAPI
from app.db import init_db
from app.db_runtime import create_db_runtime
from app.execution_persistence import ExecutionStateStore
from app.execution_observability import ExecutionObservability
from app.execution_alert_store import ExecutionAlertStore
from app.execution_alert_policy import ExecutionAlertPolicy
from app.execution_alert_service import ExecutionAlertService
from app.execution_health import ExecutionHealth
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
    execution_observability: ExecutionObservability
    execution_alert_store: ExecutionAlertStore
    execution_alert_service: ExecutionAlertService
    authorization: ExecutionAuthorization | None = None
    session_local: object | None = None
    startup_execution_state: StartupExecutionStateMachine | None = None
    emergency_halt_controller: EmergencyHaltController | None = None


def create_resources(*, execution_path="data/execution_state.json", idempotency_path="data/idempotency.sqlite3", safety_path="data/safety_state.json", audit_path="data/trading_audit.jsonl", database_url: str | None = None, alert_path="data/execution_alerts.sqlite3", execution_health_token="test-token") -> AppResources:
    session_local = None
    if database_url:
        _, session_local = create_db_runtime(database_url)
    safety_store = SafetyStateStore(safety_path)
    audit_log = TradingAuditLog(audit_path)
    startup_execution_state = StartupExecutionStateMachine(audit_log)
    emergency_halt_controller = EmergencyHaltController(safety_store, startup_execution_state, audit_log)
    authorization = ExecutionAuthorization(safety_store, audit_log=audit_log)
    observability = ExecutionObservability()
    alert_store = ExecutionAlertStore(alert_path)
    alert_service = ExecutionAlertService(ExecutionHealth(observability), ExecutionAlertPolicy(), alert_store)
    observability.add_hook(alert_service.evaluate)
    return AppResources(
        execution_store=ExecutionStateStore(execution_path),
        idempotency_store=IdempotencyStore(idempotency_path),
        safety_store=safety_store,
        audit_log=audit_log,
        execution_observability=observability,
        execution_alert_store=alert_store,
        execution_alert_service=alert_service,
        authorization=authorization,
        session_local=session_local,
        startup_execution_state=startup_execution_state,
        emergency_halt_controller=emergency_halt_controller,
    )


def create_app(resources: AppResources | None = None, broker_router: BrokerRouter | None = None, execution_health_token: str | None = None) -> FastAPI:
    resources = resources or create_resources(execution_health_token=execution_health_token or "test-token")
    app = FastAPI(title="AI Trading Platform", version="1.0.0")
    app.state.resources = resources
    app.state.execution_observability = resources.execution_observability
    app.state.execution_alert_store = resources.execution_alert_store
    app.state.execution_alert_service = resources.execution_alert_service
    app.state.execution_health_token = execution_health_token if execution_health_token is not None else "test-token"
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
    from app.api.execution_health import router as execution_health_router
    from app.api.execution_alerts import router as execution_alerts_router
    app.include_router(orders_router)
    app.include_router(decision_router)
    app.include_router(execution_health_router)
    app.include_router(execution_alerts_router)
    return app
