from __future__ import annotations

from dataclasses import dataclass
from fastapi import FastAPI
from app.db import init_db
from app.db_runtime import create_db_runtime
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.safety_state import SafetyStateStore
from app.broker_factory import build_broker_router
from app.broker_router import BrokerRouter
from app.execution_authorization import ExecutionAuthorization


@dataclass
class AppResources:
    execution_store: ExecutionStateStore
    idempotency_store: IdempotencyStore
    safety_store: SafetyStateStore
    authorization: ExecutionAuthorization | None = None
    session_local: object | None = None


def create_resources(*, execution_path="data/execution_state.json", idempotency_path="data/idempotency.sqlite3", safety_path="data/safety_state.json", database_url: str | None = None) -> AppResources:
    session_local = None
    safety_store = SafetyStateStore(safety_path)
    return AppResources(
        execution_store=ExecutionStateStore(execution_path),
        idempotency_store=IdempotencyStore(idempotency_path),
        safety_store=safety_store,
        authorization=ExecutionAuthorization(safety_store),
        session_local=session_local,
    )


def create_app(resources: AppResources | None = None, broker_router: BrokerRouter | None = None) -> FastAPI:
    resources = resources or create_resources()
    app = FastAPI(title="AI Trading Platform", version="1.0.0")
    app.state.resources = resources
    app.state.broker_router = broker_router or build_broker_router(resources.safety_store)

    @app.on_event("startup")
    async def startup() -> None:
        if resources.session_local is None:
            init_db()

    from app.api.orders import router as orders_router
    from app.api.ensemble import router as decision_router
    app.include_router(orders_router)
    app.include_router(decision_router)
    return app
