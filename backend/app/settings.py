from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./trading.db"
    jwt_secret: str = "change-me-in-production"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
