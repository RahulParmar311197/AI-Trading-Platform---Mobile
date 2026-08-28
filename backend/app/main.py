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
    app.state.safety_store = safety_store
    app.state.trading_health = trading_health
    app.state.trading_metrics = trading_metrics
    app.state.risk_circuit_breaker = risk_circuit_breaker
    init_db()
    lifecycle = OrderLifecycle(resources.audit_log)
    app.state.order_lifecycle = lifecycle
    with SessionLocal() as session:
        reconcile_api_order_projection(session, lifecycle)
        active_accounts = session.query(BrokerAccount).filter(BrokerAccount.status == "active").all()
        if len(active_accounts) == 1:
            provision_active_account_routes(execution_broker_router, active_accounts)
        elif len(active_accounts) > 1:
            safety_store.halt("MULTI_ACCOUNT_RECONCILIATION_REQUIRED")
    yield


app = FastAPI(title="AI Trading Platform", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in [
    auth_router,
    broker_accounts_router,
    upstox_oauth_router,
    emergency_halt_router,
    orders_router,
    health_router,
    execution_health_router,
    create_operational_router(trading_health, trading_metrics),
    create_risk_circuit_router(risk_circuit_breaker),
]:
    app.include_router(router)
