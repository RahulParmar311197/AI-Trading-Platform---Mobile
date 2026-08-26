from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ensure_compatibility_columns() -> None:
    """Add nullable safety columns to existing deployments before they serve traffic."""
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("orders")}
    if "broker_route_generation" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE orders ADD COLUMN broker_route_generation VARCHAR(160)"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_compatibility_columns()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
