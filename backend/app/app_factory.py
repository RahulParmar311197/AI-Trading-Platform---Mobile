from __future__ import annotations

import asyncio
from dataclasses import dataclass
from fastapi import FastAPI
from app.db import init_db, SessionLocal
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
from app.broker_context_attestation import BrokerContextAttestor
from app.execution_authorization import ExecutionAuthorization
from app.execution_authorization_store import ExecutionAuthorizationStore
from app.live_execution_gateway import LiveExecutionGateway, ExecutionPolicy
from app.authoritative_live_execution_gateway import AuthoritativeLiveExecutionGateway
from app.reconciliation import ReconciliationEngine
from app.reconciliation_coordinator import ReconciliationCoordinator
from app.startup_execution_state import StartupExecutionStateMachine
from app.submission_intent_store import SubmissionIntentStore
from app.risk_reservation_store import RiskReservationStore
from app.ai_execution_orchestrator import AIExecutionOrchestrator
from app.trading_audit import TradingAuditLog
from app.emergency_halt import EmergencyHaltController
from app.broker_connectivity_registry import BrokerConnectivityRegistry
from app.broker_health_worker import BrokerHealthWorker
from app.settings import settings


_DEFAULT_ATTESTATION_SECRET = b"test-broker-context-attestation-secret-32+"


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
    connectivity_registry: BrokerConnectivityRegistry
    broker_context_attestor: BrokerContextAttestor
    execution_authorization_store: ExecutionAuthorizationStore
    submission_intent_store: SubmissionIntentStore
    risk_reservation_store: RiskReservationStore | None = None
    authorization: ExecutionAuthorization | None = None
    session_local: object | None = None
    startup_execution_state: StartupExecutionStateMachine | None = None
    emergency_halt_controller: EmergencyHaltController | None = None
    execution_health_token: str | None = None

    def create_reconciliation_coordinator(self, *, engine: ReconciliationEngine, route: str, account_id: str, route_generation: str, generation: int = 0) -> ReconciliationCoordinator:
        return ReconciliationCoordinator(engine=engine, route=route, account_id=account_id, route_generation=route_generation, context_attestor=self.broker_context_attestor, generation=generation)

    def create_live_execution_gateway(self, executor, *, policy: ExecutionPolicy | None = None, position_reader=None, local_positions_reader=None, incident_reporter=None) -> LiveExecutionGateway:
        return AuthoritativeLiveExecutionGateway(executor, policy=policy, position_reader=position_reader, local_positions_reader=local_positions_reader, incident_reporter=incident_reporter, authorization_store=self.execution_authorization_store, context_attestor=self.broker_context_attestor, submission_intent_store=self.submission_intent_store)

    def create_ai_execution_orchestrator(self, *, decision_engine, instrument_provider, order_submitter=None, intent_config=None) -> AIExecutionOrchestrator:
        """Create the canonical AI execution boundary with durable risk reservations."""
        if order_submitter is None:
            raise ValueError("order_submitter is required for AI execution")
        if self.risk_reservation_store is None:
            raise RuntimeError("durable risk reservation store is unavailable; AI execution is blocked")
        return AIExecutionOrchestrator(decision_engine=decision_engine, instrument_provider=instrument_provider, order_submitter=order_submitter, intent_config=intent_config, risk_reservation_store=self.risk_reservation_store)


def create_resources(*, execution_path="data/execution_state.json", idempotency_path="data/idempotency.sqlite3", safety_path="data/safety_state.json", audit_path="data/trading_audit.jsonl", database_url: str | None = None, alert_path="data/execution_alerts.sqlite3", alert_event_path="data/execution_alert_events.sqlite3", execution_authorization_path="data/execution_authorizations.sqlite3", submission_intent_path="data/submission_intents.json", execution_health_token: str | None = None, broker_context_attestation_secret: bytes | str | None = None) -> AppResources:
    session_local = None
    if database_url:
        _, session_local = create_db_runtime(database_url)
    elif not settings.database_url.lower().startswith("sqlite"):
        session_local = SessionLocal
    safety_store = SafetyStateStore(safety_path)
    audit_log = TradingAuditLog(audit_path)
    startup_execution_state = StartupExecutionStateMachine(audit_log)
    emergency_halt_controller = EmergencyHaltController(safety_store, startup_execution_state, audit_log)
    authorization = ExecutionAuthorization(safety_store, audit_log=audit_log)
    attestation_secret = broker_context_attestation_secret or _DEFAULT_ATTESTATION_SECRET
    if isinstance(attestation_secret, str):
        attestation_secret = attestation_secret.encode("utf-8")
    broker_context_attestor = BrokerContextAttestor(attestation_secret)
    execution_authorization_store = ExecutionAuthorizationStore(execution_authorization_path)
    submission_intent_store = SubmissionIntentStore(submission_intent_path, session_factory=session_local)
    risk_reservation_store = RiskReservationStore(session_local) if session_local is not None else None
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
    return AppResources(execution_store=ExecutionStateStore(execution_path), idempotency_store=IdempotencyStore(idempotency_path), safety_store=safety_store, audit_log=audit_log, execution_observability=observability, execution_alert_store=alert_store, execution_alert_service=alert_service, execution_alert_recovery=recovery, execution_alert_event_store=event_store, execution_alert_event_publisher=event_publisher, execution_alert_dispatcher=dispatcher, execution_alert_worker=worker, execution_alert_worker_health=worker_health, execution_alert_dead_letter_store=dead_letter_store, connectivity_registry=BrokerConnectivityRegistry(), broker_context_attestor=broker_context_attestor, execution_authorization_store=execution_authorization_store, submission_intent_store=submission_intent_store, risk_reservation_store=risk_reservation_store, authorization=authorization, session_local=session_local, startup_execution_state=startup_execution_state, emergency_halt_controller=emergency_halt_controller, execution_health_token=execution_health_token)


def create_app(resources: AppResources | None = None, broker_router: BrokerRouter | None = None, execution_health_token: str | None = None) -> FastAPI:
    resources = resources or create_resources(execution_health_token=execution_health_token)
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
    app.state.execution_health_token = execution_health_token if execution_health_token is not None else resources.execution_health_token
    app.state.broker_context_attestor = resources.broker_context_attestor
    app.state.execution_authorization_store = resources.execution_authorization_store
    app.state.submission_intent_store = resources.submission_intent_store
    app.state.risk_reservation_store = resources.risk_reservation_store
    app.state.broker_router = broker_router or build_broker_router(resources.safety_store, context_attestor=resources.broker_context_attestor)
    app.state.startup_execution_state = resources.startup_execution_state
    app.state.emergency_halt_controller = resources.emergency_halt_controller
    app.state.trading_audit_log = resources.audit_log
    app.state.broker_health_worker = None
    app.state.broker_health_stop_event = None
    app.state.broker_health_task = None

    @app.on_event("startup")
    async def startup() -> None:
        if resources.session_local is None:
            init_db()
        stop_event = asyncio.Event()
        health_worker = BrokerHealthWorker(app.state.broker_router, resources.connectivity_registry, readiness_check=lambda: resources.startup_execution_state is not None and resources.startup_execution_state.execution_allowed)
        app.state.broker_health_worker = health_worker
        app.state.broker_health_stop_event = stop_event
        app.state.broker_health_task = asyncio.create_task(health_worker.run(stop_event), name="broker-health-worker")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        stop_event = app.state.broker_health_stop_event
        task = app.state.broker_health_task
        if stop_event is not None:
            stop_event.set()
        if task is not None:
            await task
        app.state.broker_health_task = None
        app.state.broker_health_stop_event = None
        app.state.broker_health_worker = None

    from app.api.orders import router as orders_router
    from app.api.ensemble import router as decision_router
    from app.api.execution_health import router as execution_health_router
    from app.api.execution_alerts import router as execution_alerts_router
    from app.api.execution_alert_lifecycle import router as execution_alert_lifecycle_router
    from app.api.execution_alert_dashboard import router as execution_alert_dashboard_router
    from app.api.execution_alert_events import router as execution_alert_events_router
    from app.api.execution_alert_operations import router as execution_alert_operations_router
    from app.api.execution_alert_worker_health import router as execution_alert_worker_health_router
    from app.api.execution_notification_health import router as execution_notification_health_router
    from app.api.mobile_notification_health import router as mobile_notification_health_router
    app.include_router(orders_router)
    app.include_router(decision_router)
    app.include_router(execution_health_router)
    app.include_router(execution_alerts_router)
    app.include_router(execution_alert_lifecycle_router)
    app.include_router(execution_alert_dashboard_router)
    app.include_router(execution_alert_events_router)
    app.include_router(execution_alert_operations_router)
    app.include_router(execution_alert_worker_health_router)
    app.include_router(execution_notification_health_router)
    app.include_router(mobile_notification_health_router)
    return app
