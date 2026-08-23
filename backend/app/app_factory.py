from __future__ import annotations

from dataclasses import dataclass
from fastapi import FastAPI
from app.db import init_db
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.safety_state import SafetyStateStore
from app.broker_factory import build_broker_router


@dataclass
class AppResources:
    execution_store: ExecutionStateStore
    idempotency_store: IdempotencyStore
    safety_store: SafetyStateStore


def create_resources(*, execution_path="data/execution_state.json", idempotency_path="data/idempotency.sqlite3", safety_path="data/safety_state.json") -> AppResources:
    return AppResources(
        execution_store=ExecutionStateStore(execution_path),
        idempotency_store=IdempotencyStore(idempotency_path),
        safety_store=SafetyStateStore(safety_path),
    )


def create_app(resources: AppResources | None = None) -> FastAPI:
    resources = resources or create_resources()
    app = FastAPI(title="AI Trading Platform", version="1.0.0")
    app.state.resources = resources
    app.state.broker_router = build_broker_router(resources.safety_store)

    @app.on_event("startup")
    async def startup() -> None:
        init_db()

    from app.api.orders import router as orders_router
    app.include_router(orders_router)
    return app
