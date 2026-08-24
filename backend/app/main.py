from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai import router as ai_router
from app.api.ai_strategy import router as ai_strategy_router
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.backtest import router as backtest_router
from app.api.backtest_engine import router as backtest_engine_router
from app.api.broker import router as broker_router
from app.api.api_placeholder import router as placeholder_router
