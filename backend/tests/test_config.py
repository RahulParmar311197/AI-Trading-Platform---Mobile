from app.config import get_settings


def test_settings_are_cached_and_have_safe_defaults(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.environment == "development"
    assert settings.live_trading_enabled is False
    assert settings.cors_origin_list
    assert get_settings() is settings

    get_settings.cache_clear()
