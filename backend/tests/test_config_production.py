import pytest

from app.config import Settings


def production_env(database_url: str) -> dict:
    return {
        "ENVIRONMENT": "production",
        "DATABASE_URL": database_url,
        "EXECUTION_HEALTH_TOKEN": "x" * 32,
        "JWT_SECRET": "production-jwt-secret" * 2,
        "BROKER_CONTEXT_ATTESTATION_SECRET": "y" * 32,
    }


def test_production_rejects_sqlite(monkeypatch):
    for key, value in production_env("sqlite:///./trading.db").items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match="DATABASE_URL must use a server database in production"):
        Settings()


def test_production_accepts_server_database(monkeypatch):
    for key, value in production_env("postgresql+asyncpg://user:pass@db/trading").items():
        monkeypatch.setenv(key, value)

    settings = Settings()
    assert settings.is_production is True
    assert settings.database_url.startswith("postgresql+asyncpg://")
