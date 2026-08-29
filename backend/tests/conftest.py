import os

# Configure non-production test settings before test modules import app.main.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("BROKER_CONTEXT_ATTESTATION_SECRET", "test-broker-context-attestation-secret-32-bytes-min")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture(autouse=True)
def isolated_test_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("SAFETY_STATE_PATH", str(tmp_path / "safety.json"))
    monkeypatch.setenv("EXECUTION_STATE_PATH", str(tmp_path / "execution.json"))
    monkeypatch.setenv("IDEMPOTENCY_STATE_PATH", str(tmp_path / "idempotency.sqlite3"))


@pytest.fixture
def test_session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fixture.sqlite3'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        yield SessionLocal
    finally:
        engine.dispose()
