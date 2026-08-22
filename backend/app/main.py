from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.markets import router as markets_router
from app.api.analysis import router as analysis_router
from app.api.backtest import router as backtest_router
from app.api.paper import router as paper_router
from app.api.risk import router as risk_router
from app.api.replay import router as replay_router
from app.api.auth import router as auth_router
from app.api.stream import router as stream_router
from app.api.portfolio import router as portfolio_router
from app.api.notifications import router as notifications_router
from app.api.orders import router as orders_router
from app.api.market_data import router as market_data_router
from app.api.confluence import router as confluence_router
from app.api.signals import router as signals_router
from app.api.paper_execution import router as paper_execution_router
from app.api.backtest_engine import router as backtest_engine_router
from app.api.scanner import router as scanner_router
from app.api.options import router as options_router
from app.api.risk_engine import router as risk_engine_router
from app.api.journal import router as journal_router
from app.api.ai import router as ai_router
from app.api.ensemble import router as ensemble_router
from app.api.ml_training import router as ml_training_router
from app.api.model_registry import router as model_registry_router
from app.api.walk_forward import router as walk_forward_router
from app.api.ml_trainer import router as ml_trainer_router
from app.api.strategy_backtest import router as strategy_backtest_router
from app.api.ict_smc import router as ict_smc_router
from app.api.mtf_analysis import router as mtf_analysis_router
from app.api.ict_zones import router as ict_zones_router
from app.api.ensemble_v2 import router as ensemble_v2_router
from app.api.mtf_ensemble import router as mtf_ensemble_router
from app.api.unified_backtest import router as unified_backtest_router
from app.api.trade_risk import router as trade_risk_router
from app.api.execution_lifecycle import router as execution_lifecycle_router
from app.api.position_manager import router as position_manager_router
from app.api.protection_engine import router as protection_engine_router
from app.api.broker import router as broker_router
from app.api.reconciliation import router as reconciliation_router
from app.api.market_data_normalizer import router as market_data_normalizer_router
from app.api.mtf_aggregator import router as mtf_aggregator_router
from app.api.realtime_market_stream import router as realtime_market_stream_router
from app.api.candle_builder import router as candle_builder_router
from app.api.stream_pipeline import router as stream_pipeline_router
from app.api.historical_market_store import router as historical_market_store_router
from app.api.historical_backfill import router as historical_backfill_router
from app.db import init_db
app=FastAPI(title="AI Trading Platform API",version="4.5.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
for router,prefix in [(health_router,""),(markets_router,"/api"),(analysis_router,"/api"),(backtest_router,"/api"),(paper_router,"/api"),(risk_router,"/api"),(replay_router,"/api"),(auth_router,"/api"),(portfolio_router,"/api"),(notifications_router,"/api"),(backtest_engine_router,""),(strategy_backtest_router,""),(unified_backtest_router,""),(risk_engine_router,""),(orders_router,""),(market_data_router,""),(confluence_router,""),(signals_router,""),(paper_execution_router,""),(scanner_router,""),(options_router,""),(journal_router,""),(ai_router,""),(ensemble_router,""),(ml_training_router,""),(model_registry_router,""),(walk_forward_router,""),(ml_trainer_router,""),(ict_smc_router,""),(mtf_analysis_router,""),(ict_zones_router,""),(ensemble_v2_router,""),(mtf_ensemble_router,""),(trade_risk_router,""),(execution_lifecycle_router,"/"),(position_manager_router,""),(protection_engine_router,""),(broker_router,""),(reconciliation_router,""),(market_data_normalizer_router,""),(mtf_aggregator_router,""),(realtime_market_stream_router,""),(candle_builder_router,""),(stream_pipeline_router,""),(historical_market_store_router,""),(historical_backfill_router,"")]: app.include_router(router,prefix=prefix)
app.include_router(stream_router)
@app.on_event("startup")
def startup(): init_db()
@app.get("/")
def root(): return {"name":"AI Trading Platform","version":"4.5.0","status":"ok"}
