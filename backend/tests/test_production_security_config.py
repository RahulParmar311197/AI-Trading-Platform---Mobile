import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_requires_strong_execution_health_token():
    with pytest.raises(ValidationError):
        Settings(environment="production", execution_health_token="short", jwt_secret="not-default")


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(environment="production", execution_health_token="x" * 32)


def test_development_allows_empty_execution_health_token():
    settings = Settings(environment="development", execution_health_token="", jwt_secret="change-me-in-production")
    assert settings.execution_health_token == ""
