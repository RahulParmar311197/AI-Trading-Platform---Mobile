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
from app.ai_intelligence_api import router as ai_intelligence_router
from app.api.ai import router as ai_router
from app.api.ai_strategy import router as ai_strategy_router
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.backtest import router as backtest_router
from app.api.backtest_engine import router as backtest_engine_router
from app.api.broker import router as broker_api_router
from app.api.broker_accounts import router as broker_accounts_router
from app.api.broker_connection import router as broker_connection_router
from app.api.broker_account_state import router as broker_account_state_router
from app.api.portfolio_state_api import router as portfolio_state_router
from app.api.upstox_oauth import router as upstox_oauth_router
from app.api.upstox_oauth_complete import router as upstox_oauth_complete_router
from app.api.candle_builder import router as candle_builder_router
from app.api.confluence import router as confluence_router
from app.api.data_provider import router as data_provider_router
from app.api.ensemble import router as ensemble_router
from app.api.ensemble_v2 import router as ensemble_v2_router
from app.api.execution_lifecycle import router as execution_lifecycle_router
from app.api.historical_backfill import router as historical_backfill_router
from app.api.historical_market_store import router as historical_market_store_router
from app.api.health import router as health_router
from app.api.ict_smc import router as ict_smc_router
from app.api.ict_zones import router as ict_zones_router
from app.api.journal import router as journal_router
from app.api.market_data import router as market_data_router
from app.api.market_data_normalizer import router as market_data_normalizer_router
from app.api.markets import router as markets_router
from app.api.ml_trainer import router as ml_trainer_router
from app.api.ml_training import router as ml_training_router
from app.api.model_registry import router as model_registry_router
from app.api.mtf_aggregator import router as mtf_aggregator_router
from app.api.mtf_analysis import router as mtf_analysis_router
from app.api.mtf_ensemble import router as mtf_ensemble_router
from app.api.notifications import router as notifications_router
from app.api.options import router as options_router
from app.api.orders import router as orders_router
from app.api.paper import router as paper_router
from app.api.paper_execution import router as paper_execution_router
from app.api.portfolio import router as portfolio_router
from app.api.position_manager import router as position_manager_router
from app.api.protection_engine import router as protection_engine_router
from app.api.realtime_market_stream import router as realtime_market_stream_router
from app.api.reconciliation import router as reconciliation_router
from app.api.recovery import router as recovery_router
from app.api.replay import router as replay_router
from app.api.risk import router as risk_router
from app.api.risk_engine import router as risk_engine_router
from app.api.scanner import router as scanner_router
from app.api.signals import router as signals_router
from app.api.strategy_backtest import router as strategy_backtest_router
from app.api.stream import router as stream_router
from app.api.stream_pipeline import router as stream_pipeline_router
from app.api.trade_risk import router as trade_risk_router
from app.api.unified_backtest import router as unified_backtest_router
from app.api.walk_forward import router as walk_forward_router

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
        startup_state.transition(StartupExecutionState.RECOVERING)
        result=broker_recovery.run(lifecycle); app.state.recovery_result=result
        if not result.ready: startup_state.fail('broker startup recovery failed')
        else:
            startup_state.transition(StartupExecutionState.BROKER_RECONCILED); local_positions=_persisted_local_positions(lifecycle)
            try: broker_positions=execution_broker_router.get_positions(); broker_error=None
            except Exception as exc: broker_positions=None; broker_error=str(exc)
            if broker_positions is None: startup_state.fail(f'broker position snapshot unavailable: {broker_error or "unknown error"}'); app.state.startup_gate_result=None
            else:
                gate_result=startup_gate.evaluate(local_positions,broker_positions); app.state.startup_gate_result=gate_result
                if not gate_result.ready: startup_state.fail('portfolio reconciliation failed')
                else:
                    startup_state.transition(StartupExecutionState.PORTFOLIO_RECONCILED); startup_state.transition(StartupExecutionState.RISK_READY); startup_state.transition(StartupExecutionState.READY)
    yield

app=FastAPI(title='AI Trading Platform',version='1.0.0',lifespan=lifespan); app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
for router in [emergency_halt_router,ai_router,ai_strategy_router,ai_intelligence_router,analysis_router,auth_router,backtest_router,backtest_engine_router,broker_api_router,broker_accounts_router,broker_connection_router,broker_account_state_router,portfolio_state_router,upstox_oauth_router,upstox_oauth_complete_router,candle_builder_router,confluence_router,data_provider_router,ensemble_router,ensemble_v2_router,execution_lifecycle_router,historical_backfill_router,historical_market_store_router,health_router,ict_smc_router,ict_zones_router,journal_router,market_data_router,market_data_normalizer_router,markets_router,ml_trainer_router,ml_training_router,model_registry_router,mtf_aggregator_router,mtf_analysis_router,mtf_ensemble_router,notifications_router,options_router,orders_router,paper_router,paper_execution_router,portfolio_router,position_manager_router,protection_engine_router,realtime_market_stream_router,reconciliation_router,recovery_router,replay_router,risk_router,risk_engine_router,scanner_router,signals_router,strategy_backtest_router,stream_router,stream_pipeline_router,trade_risk_router,unified_backtest_router,walk_forward_router]: app.include_router(router)