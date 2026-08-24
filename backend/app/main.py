from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.emergency_halt import router as emergency_halt_router
from app.app_factory import create_resources
from app.broker_factory import build_broker_router
from app.broker_recovery import BrokerStartupRecovery
from app.config import get_settings
from app.db import init_db
from app.order_lifecycle import OrderLifecycle
from app.recovery_manager import StartupRecoveryManager
from app.startup_reconciliation_gate import StartupReconciliationGate
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine
from app.portfolio_reconciliation_service import PortfolioReconciliationService
from app.emergency_halt import EmergencyHaltController
from app.api.health import router as health_router

settings=get_settings(); resources=create_resources(); execution_store=resources.execution_store; idempotency_store=resources.idempotency_store; safety_store=resources.safety_store
execution_broker_router=build_broker_router(safety_store); recovery_manager=StartupRecoveryManager(execution_store,safety_store); broker_recovery=BrokerStartupRecovery(execution_broker_router,execution_store,safety_store,recovery_manager); startup_state=resources.startup_execution_state; emergency_halt_controller=resources.emergency_halt_controller; startup_gate=StartupReconciliationGate(startup_state,safety_store,PortfolioReconciliationService())

def _persisted_local_positions(lifecycle: OrderLifecycle) -> dict[str,float]:
    positions={}
    for symbol,position in lifecycle.positions.items():
        quantity=float(position.quantity or 0.0); side=str(position.side or '').upper(); signed=-abs(quantity) if side in {'SELL','SHORT'} else abs(quantity); key=str(symbol).strip().upper()
        if key: positions[key]=positions.get(key,0.0)+signed
    return {symbol:quantity for symbol,quantity in positions.items() if abs(quantity)>1e-9}

@asynccontextmanager
async def lifespan(app:FastAPI):
    app.state.resources=resources; app.state.broker_router=execution_broker_router; app.state.startup_execution_state=startup_state; app.state.emergency_halt_controller=emergency_halt_controller; app.state.trading_audit_log=resources.audit_log; init_db(); lifecycle=OrderLifecycle(resources.audit_log); app.state.order_lifecycle=lifecycle
    if emergency_halt_controller.is_halted():
        startup_state.halt(safety_store.load().halt_reason or 'persisted emergency halt')
    else:
        startup_state.transition(StartupExecutionState.RECOVERING, 'application startup recovery')
        result=broker_recovery.run(lifecycle); app.state.recovery_result=result
        if not result.ready:
            startup_state.fail('broker startup recovery failed')
        else:
            startup_state.transition(StartupExecutionState.BROKER_RECONCILED, 'broker orders reconciled')
            local_positions=_persisted_local_positions(lifecycle)
            try: broker_positions=execution_broker_router.get_positions(); broker_error=None
            except Exception as exc: broker_positions=None; broker_error=str(exc)
            if broker_positions is None:
                startup_state.fail(f'broker position snapshot unavailable: {broker_error or "unknown error"}')
                app.state.startup_gate_result=None
            else:
                gate_result=startup_gate.evaluate(local_positions,broker_positions); app.state.startup_gate_result=gate_result
                if not gate_result.ready:
                    startup_state.fail('portfolio reconciliation failed')
                else:
                    startup_state.transition(StartupExecutionState.PORTFOLIO_RECONCILED, 'portfolio reconciled')
                    startup_state.transition(StartupExecutionState.RISK_READY, 'risk readiness checks passed')
                    startup_state.transition(StartupExecutionState.READY)
    yield

app=FastAPI(title='AI Trading Platform',version='1.0.0',lifespan=lifespan); app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
for router in [emergency_halt_router,health_router]: app.include_router(router)
