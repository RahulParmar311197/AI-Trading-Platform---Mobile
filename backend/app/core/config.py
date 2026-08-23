from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Trading Platform"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://trader:trader@db:5432/trading"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "change-me"
    jwt_exp_minutes: int = 60
    cors_origins: str = "*"
    recovery_admin_username: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
