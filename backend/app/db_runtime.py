from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


def create_db_runtime(database_url: str):
    connect_args = {}
    engine_kwargs = {"pool_pre_ping": True}

    if database_url.startswith("sqlite:"):
        connect_args["check_same_thread"] = False
        engine_kwargs["connect_args"] = connect_args

    engine = create_engine(database_url, **engine_kwargs)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    return engine, SessionLocal
