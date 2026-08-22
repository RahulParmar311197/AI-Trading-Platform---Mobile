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
from app.db import init_db

app = FastAPI(title="AI Trading Platform API", version="1.8.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(health_router)
app.include_router(markets_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(backtest_engine_router)
app.include_router(paper_router, prefix="/api")
app.include_router(risk_router, prefix="/api")
app.include_router(replay_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(orders_router)
app.include_router(market_data_router)
app.include_router(confluence_router)
app.include_router(signals_router)
app.include_router(paper_execution_router)
app.include_router(scanner_router)
app.include_router(stream_router)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"name": "AI Trading Platform", "version": "1.8.0", "status": "ok"}
