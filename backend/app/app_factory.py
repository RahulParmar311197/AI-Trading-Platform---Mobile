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
from app.execution_alert_resolution import ExecutionAlertResolutionService
from app.execution_alert_recovery import ExecutionAlertRecoveryCoordinator
from app.execution_alert_events import ExecutionAlertEventPublisher, ExecutionAlertEventStore
from app.execution_alert_dispatcher import ExecutionAlertDispatcher
from app.execution_alert_worker import ExecutionAlertOutboxWorker
from app.execution_alert_worker_health import ExecutionAlertWorkerHealth
from app.execution_alert_dead_letter import ExecutionAlertDeadLetterStore
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
    execution_alert_recovery: ExecutionAlertRecoveryCoordinator
    execution_alert_event_store: ExecutionAlertEventStore
    execution_alert_event_publisher: ExecutionAlertEventPublisher
    execution_alert_dispatcher: ExecutionAlertDispatcher
    execution_alert_worker: ExecutionAlertOutboxWorker
    execution_alert_worker_health: ExecutionAlertWorkerHealth
    execution_alert_dead_letter_store: ExecutionAlertDeadLetterStore
    authorization: ExecutionAuthorization | None = None
    session_local: object | None = None
    startup_execution_state: StartupExecutionStateMachine | None = None
    emergency_halt_controller: EmergencyHaltController | None = None


def create_resources(*, execution_path="data/execution_state.json", idempotency_path="data/idempotency.sqlite3", safety_path="data/safety_state.json", audit_path="data/trading_audit.jsonl", database_url: str | None = None, alert_path="data/execution_alerts.sqlite3", alert_event_path="data/execution_alert_events.sqlite3", execution_health_token="test-token") -> AppResources:
    session_local = None
    if database_url:
        _, session_local = create_db_runtime(database_url)
    safety_store = SafetyStateStore(safety_path)
    audit_log = TradingAuditLog(audit_path)
    startup_execution_state = StartupExecutionStateMachine(audit_log)
    emergency_halt_controller = EmergencyHaltController(safety_store, startup_execution_state, audit_log)
    authorization = ExecutionAuthorization(safety_store, audit_log=audit_log)
    observability = ExecutionObservability()
    health = ExecutionHealth(observability)
    event_store = ExecutionAlertEventStore(alert_event_path)
    event_publisher = ExecutionAlertEventPublisher(event_store)
    alert_store = ExecutionAlertStore(alert_path, event_publisher=event_publisher)
    alert_service = ExecutionAlertService(health, ExecutionAlertPolicy(), alert_store)
    recovery = ExecutionAlertRecoveryCoordinator(ExecutionAlertResolutionService(health, alert_store))
    dispatcher = ExecutionAlertDispatcher(event_store)
    worker = ExecutionAlertOutboxWorker(dispatcher)
    worker_health = ExecutionAlertWorkerHealth(alert_event_path)
    dead_letter_store = ExecutionAlertDeadLetterStore(alert_event_path)
    observability.add_hook(alert_service.evaluate, priority=100)
    observability.add_hook(recovery.evaluate, priority=200)
    return AppResources(ExecutionStateStore(execution_path), IdempotencyStore(idempotency_path), safety_store, audit_log, observability, alert_store, alert_service, recovery, event_store, event_publisher, dispatcher, worker, worker_health, dead_letter_store, authorization, session_local, startup_execution_state, emergency_halt_controller)


def create_app(resources: AppResources | None = None, broker_router: BrokerRouter | None = None, execution_health_token: str | None = None) -> FastAPI:
    resources = resources or create_resources(execution_health_token=execution_health_token or "test-token")
    app = FastAPI(title="AI Trading Platform", version="1.0.0")
    app.state.resources = resources
    app.state.execution_observability = resources.execution_observability
    app.state.execution_alert_store = resources.execution_alert_store
    app.state.execution_alert_service = resources.execution_alert_service
    app.state.execution_alert_recovery = resources.execution_alert_recovery
    app.state.execution_alert_event_store = resources.execution_alert_event_store
    app.state.execution_alert_event_publisher = resources.execution_alert_event_publisher
    app.state.execution_alert_dispatcher = resources.execution_alert_dispatcher
    app.state.execution_alert_worker = resources.execution_alert_worker
    app.state.execution_alert_worker_health = resources.execution_alert_worker_health
    app.state.execution_alert_dead_letter_store = resources.execution_alert_dead_letter_store
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
    from app.api.execution_alert_lifecycle import router as execution_alert_lifecycle_router
    from app.api.execution_alert_dashboard import router as execution_alert_dashboard_router
    from app.api.execution_alert_events import router as execution_alert_events_router
    from app.api.execution_alert_operations import router as execution_alert_operations_router
    from app.api.execution_alert_worker_health import router as execution_alert_worker_health_router
    app.include_router(orders_router)
    app.include_router(decision_router)
    app.include_router(execution_health_router)
    app.include_router(execution_alerts_router)
    app.include_router(execution_alert_lifecycle_router)
    app.include_router(execution_alert_dashboard_router)
    app.include_router(execution_alert_events_router)
    app.include_router(execution_alert_operations_router)
    app.include_router(execution_alert_worker_health_router)
    return app
