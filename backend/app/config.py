from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "AI Trading Platform API"
    app_version: str = "4.7.0"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8000", validation_alias="CORS_ORIGINS")
    database_url: str = Field(default="sqlite:///./trading.db", validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    jwt_secret: str = Field(default="change-me-in-production", validation_alias="JWT_SECRET")
    jwt_exp_minutes: int = Field(default=60, validation_alias="JWT_EXP_MINUTES")
    live_trading_enabled: bool = Field(default=False, validation_alias="LIVE_TRADING_ENABLED")
    broker_credentials_key: str = Field(default="", validation_alias="BROKER_CREDENTIALS_KEY")
    upstox_client_id: str = Field(default="", validation_alias="UPSTOX_CLIENT_ID")
    upstox_client_secret: str = Field(default="", validation_alias="UPSTOX_CLIENT_SECRET")
    upstox_redirect_uri: str = Field(default="", validation_alias="UPSTOX_REDIRECT_URI")
    risk_max_order_quantity: float = Field(default=10.0, validation_alias="RISK_MAX_ORDER_QUANTITY")
    risk_max_position_quantity: float = Field(default=20.0, validation_alias="RISK_MAX_POSITION_QUANTITY")
    risk_max_daily_loss: float = Field(default=1000.0, validation_alias="RISK_MAX_DAILY_LOSS")
    risk_max_trade_loss: float = Field(default=200.0, validation_alias="RISK_MAX_TRADE_LOSS")
    risk_trading_day_timezone: str = Field(default="Asia/Kolkata", validation_alias="RISK_TRADING_DAY_TIMEZONE")
    risk_max_snapshot_age_seconds: float = Field(default=2.0, validation_alias="RISK_MAX_SNAPSHOT_AGE_SECONDS")
    @property
    def cors_origin_list(self) -> list[str]: return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    @property
    def is_production(self) -> bool: return self.environment.lower() == "production"

@lru_cache(maxsize=1)
def get_settings() -> Settings: return Settings()
