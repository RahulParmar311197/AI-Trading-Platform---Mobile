from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.broker_accounts import router as broker_accounts_router
from app.api.emergency_halt import router as emergency_halt_router
from app.api.orders import router as orders_router
from app.api.health import router as health_router
from app.api.execution_health import router as execution_health_router
from app.app_factory import create_resources
from app.broker_factory import build_broker_router, provision_active_account_routes, validate_active_account_routes
from app.broker_recovery import BrokerStartupRecovery
from app.config import get_settings
from app.db import SessionLocal, init_db
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
execution_broker_router = build_broker_router(safety_store)
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
risk_circuit_breaker = ObservableRiskCircuitBreaker(metrics=trading_metrics, audit=resources.audit_log)


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
    init_db()
    lifecycle = OrderLifecycle(resources.audit_log)
    app.state.order_lifecycle = lifecycle

    with SessionLocal() as db:
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

    if emergency_halt_controller.is_halted():
        reason = safety_store.load().halt_reason or "persisted emergency halt"
        startup_state.halt(reason)
        trading_health.record("emergency_halt", False, reason)
    else:
        trading_health.record("emergency_halt", True, "not halted")
        startup_state.transition(
            StartupExecutionState.RECOVERING, "application startup recovery"
        )
        result = broker_recovery.run(lifecycle)
        app.state.recovery_result = result
        trading_health.record("broker_recovery", result.ready, "ready" if result.ready else "failed")
        if not result.ready:
            startup_state.fail("broker startup recovery failed")
        else:
            order_recovery = StartupOrderRecovery(
                OrderReconciliationService(execution_broker_router)
            ).run(lifecycle)
            app.state.order_recovery_result = order_recovery
            trading_health.record(
                "pending_order_recovery",
                order_recovery.ready,
                "ready" if order_recovery.ready else order_recovery.reason,
            )
            if not order_recovery.ready:
                startup_state.fail("pending order reconciliation unresolved")
            else:
                startup_state.transition(
                    StartupExecutionState.BROKER_RECONCILED, "broker orders reconciled"
                )
                with SessionLocal() as db:
                    api_order_reconciliation = reconcile_api_order_projection(db, lifecycle)
                app.state.api_order_reconciliation = api_order_reconciliation
                reconciliation_ready = not api_order_reconciliation
                trading_health.record(
                    "api_order_reconciliation",
                    reconciliation_ready,
                    "reconciled" if reconciliation_ready else "unresolved",
                )
                if api_order_reconciliation:
                    trading_metrics.increment("reconciliation_failures")
                    startup_state.fail("API order projection reconciliation unresolved")
                else:
                    local_positions = _persisted_local_positions(lifecycle)
                    try:
                        broker_positions = execution_broker_router.get_positions()
                        broker_error = None
                    except Exception as exc:
                        broker_positions = None
                        broker_error = str(exc)
                    positions_available = broker_positions is not None
                    trading_health.record(
                        "broker_position_snapshot",
                        positions_available,
                        "available" if positions_available else broker_error or "unavailable",
                    )
                    if broker_positions is None:
                        startup_state.fail(
                            f"broker position snapshot unavailable: {broker_error or 'unknown error'}"
                        )
                        app.state.startup_gate_result = None
                    else:
                        gate_result = startup_gate.evaluate(local_positions, broker_positions)
                        app.state.startup_gate_result = gate_result
                        trading_health.record(
                            "portfolio_reconciliation",
                            gate_result.ready,
                            "reconciled" if gate_result.ready else "failed",
                        )
                        if not gate_result.ready:
                            startup_state.fail("portfolio reconciliation failed")
                        else:
                            startup_state.transition(
                                StartupExecutionState.PORTFOLIO_RECONCILED,
                                "portfolio reconciled",
                            )
                            startup_state.transition(
                                StartupExecutionState.RISK_READY,
                                "risk readiness checks passed",
                            )
                            trading_health.record("risk_readiness", True, "ready")
                            startup_state.transition(StartupExecutionState.READY)

    yield


app = FastAPI(title="AI Trading Platform", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in [
    auth_router,
    broker_accounts_router,
    emergency_halt_router,
    health_router,
    execution_health_router,
    orders_router,
    create_operational_router(trading_health, trading_metrics),
    create_risk_circuit_router(risk_circuit_breaker),
]:
    app.include_router(router)
