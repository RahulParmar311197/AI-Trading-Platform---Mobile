import os

import pytest


@pytest.fixture(autouse=True)
def isolated_test_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("SAFETY_STATE_PATH", str(tmp_path / "safety.json"))
    monkeypatch.setenv("EXECUTION_STATE_PATH", str(tmp_path / "execution.json"))
    monkeypatch.setenv("IDEMPOTENCY_STATE_PATH", str(tmp_path / "idempotency.sqlite3"))
