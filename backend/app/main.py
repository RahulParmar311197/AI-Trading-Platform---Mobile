from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.broker_accounts import router as broker_accounts_router
from app.api.upstox_oauth import router as upstox_oauth_router
from app.api.emergency_halt import router as emergency_halt_router
from app.api.orders import router as orders_router
from app.api.health import router as health_router
from app.api.execution_health import router as execution_health_router
from app.app_factory import create_resources
from app.broker_factory import build_broker_router, provision_active_account_routes, validate_active_account_routes, account_route_name
from app.broker_recovery import BrokerStartupRecovery
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models.broker_account import BrokerAccount
from app.api_order_reconciliation import reconcile_api_order_projection
from app.operational_api import create_operational_router
from app.operational_metrics import TradingMetricsCollector
from app.order_lifecycle import OrderLifecycle
from app.order_reconciliation import OrderReconciliationService
from app.portfolio_reconciliation_service import PortfolioReconciliationService
from app.recovery_manager import StartupRecoveryManager
from app.risk_circuit_observability import ObservableRiskCircuitBreaker
from app.risk_circuit_api import create_risk_circuit_router
from app.startup_execution_state import StartupExecutionState
from app.startup_migrations import run_startup_migrations
from app.startup_order_recovery import StartupOrderRecovery
from app.startup_reconciliation_gate import StartupReconciliationGate
from app.system_health import TradingSystemHealth

settings = get_settings()
resources = create_resources(broker_context_attestation_secret=settings.broker_context_attestation_secret)
execution_store = resources.execution_store
idempotency_store = resources.idempotency_store
safety_store = resources.safety_store
execution_broker_router = build_broker_router(
    safety_store,
    context_attestor=resources.broker_context_attestor,
)
recovery_manager = StartupRecoveryManager(execution_store, safety_store)
broker_recovery = BrokerStartupRecovery(
    execution_broker_router, execution_store, safety_store, recovery_manager
)
startup_state = resources.startup_execution_state
emergency_halt_controller = resources.emergency_halt_controller
startup_gate = StartupReconciliationGate(
    startup_state, safety_store, PortfolioReconciliationService()
)
trading_health = TradingSystemHealth()
trading_metrics = TradingMetricsCollector()
risk_circuit_breaker = ObservableRiskCircuitBreaker(
    metrics=trading_metrics,
    audit=resources.audit_log,
    safety_store=safety_store,
)


def _persisted_local_positions(lifecycle: OrderLifecycle) -> dict[str, float]:
    positions = {}
    for symbol, position in lifecycle.positions.items():
        quantity = float(position.quantity or 0.0)
        side = str(position.side or "").upper()
        signed = -abs(quantity) if side in {"SELL", "SHORT"} else abs(quantity)
        key = str(symbol).strip().upper()
        if key:
            positions[key] = positions.get(key, 0.0) + signed
    return {symbol: quantity for symbol, quantity in positions.items() if abs(quantity) > 1e-9}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.resources = resources
    app.state.execution_observability = resources.execution_observability
    app.state.execution_health_token = settings.execution_health_token
    app.state.broker_router = execution_broker_router
    app.state.broker_context_attestor = resources.broker_context_attestor
    app.state.execution_authorization_store = resources.execution_authorization_store
    app.state.startup_execution_state = startup_state
    app.state.emergency_halt_controller = emergency_halt_controller
    app.state.trading_audit_log = resources.audit_log
    app.state.trading_health = trading_health
    app.state.trading_metrics = trading_metrics
    app.state.risk_circuit_breaker = risk_circuit_breaker

    try:
        run_startup_migrations()
    except Exception as exc:
        reason = f"startup database migration failed: {exc}"
        trading_health.record("database_migrations", False, reason)
        startup_state.fail(reason)
        yield
        return
    trading_health.record("database_migrations", True, "database is at Alembic head")

    init_db()
    lifecycle = OrderLifecycle(resources.audit_log)
    app.state.order_lifecycle = lifecycle

    with SessionLocal() as db:
        active_accounts = db.query(BrokerAccount).filter(BrokerAccount.status == "active").order_by(BrokerAccount.id.asc()).all()
        provisioning_errors = provision_active_account_routes(db, execution_broker_router)
        route_validation_errors = validate_active_account_routes(db, execution_broker_router)
    account_route_errors = provisioning_errors + route_validation_errors
    app.state.account_route_validation = account_route_errors
    if account_route_errors:
        reason = "active broker account route provisioning failed: " + "; ".join(account_route_errors)
        trading_health.record("broker_account_routes", False, reason)
        startup_state.fail(reason)
        yield
        return
    trading_health.record("broker_account_routes", True, "all active broker accounts have bound routes")

    if len(active_accounts) > 1:
        reason = "MULTI_ACCOUNT_RECONCILIATION_REQUIRED: startup recovery supports one active broker account until account-scoped safety state is available"
        trading_health.record("broker_account_reconciliation", False, reason)
        startup_state.fail(reason)
        yield
        return
    recovery_route = account_route_name(active_accounts[0]) if active_accounts else None
    app.state.recovery_route = recovery_route

    if emergency_halt_controller.is_halted():
        reason = safety_store.load().halt_reason or "persisted emergency halt"
        startup_state.halt(reason)
        trading_health.record("emergency_halt", False, reason)
    else:
        trading_health.record("emergency_halt", True, "not halted")
        startup_state.transition(
            StartupExecutionState.RECOVERING, "application startup recovery"
        )
        recovery = broker_recovery.recover(route=recovery_route)
        if not recovery.success:
            startup_state.fail(recovery.reason)
            trading_health.record("broker_recovery", False, recovery.reason)
        else:
            trading_health.record("broker_recovery", True, recovery.reason)
            if recovery_route:
                startup_order_recovery = StartupOrderRecovery(
                    execution_broker_router,
                    resources.execution_store,
                    resources.idempotency_store,
                )
                order_recovery = startup_order_recovery.recover(route=recovery_route)
                if not order_recovery.success:
                    startup_state.fail(order_recovery.reason)
                    trading_health.record("startup_order_recovery", False, order_recovery.reason)
                else:
                    trading_health.record("startup_order_recovery", True, order_recovery.reason)
                reconciliation = OrderReconciliationService(
                    execution_broker_router,
                    resources.execution_store,
                    resources.idempotency_store,
                ).reconcile(route=recovery_route)
                if not reconciliation.success:
                    startup_state.fail(reconciliation.reason)
                    trading_health.record("order_reconciliation", False, reconciliation.reason)
                else:
                    trading_health.record("order_reconciliation", True, reconciliation.reason)
                api_projection = reconcile_api_order_projection(
                    execution_broker_router,
                    resources.execution_store,
                    route=recovery_route,
                )
                if not api_projection.success:
                    startup_state.fail(api_projection.reason)
                    trading_health.record("api_order_projection", False, api_projection.reason)
                else:
                    trading_health.record("api_order_projection", True, api_projection.reason)
                with SessionLocal() as db:
                    portfolio_reconciliation = PortfolioReconciliationService().reconcile(
                        db,
                        execution_broker_router,
                        route=recovery_route,
                    )
                if not portfolio_reconciliation.success:
                    startup_state.fail(portfolio_reconciliation.reason)
                    trading_health.record("portfolio_reconciliation", False, portfolio_reconciliation.reason)
                else:
                    trading_health.record("portfolio_reconciliation", True, portfolio_reconciliation.reason)

    if startup_state.state == StartupExecutionState.FAILED:
        yield
        return
    startup_state.transition(StartupExecutionState.READY, "startup recovery and reconciliation complete")
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(broker_accounts_router)
app.include_router(upstox_oauth_router)
app.include_router(emergency_halt_router)
app.include_router(orders_router)
app.include_router(health_router)
app.include_router(execution_health_router)
app.include_router(create_operational_router(trading_health))
app.include_router(create_risk_circuit_router(risk_circuit_breaker))
