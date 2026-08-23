from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None = None
    api_secret: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 10.0
    rate_limit_per_second: float = 5.0
    retry_attempts: int = 3
    retry_base_delay_seconds: float = 0.25
    enabled: bool = True

    @classmethod
    def from_env(cls, name: str):
        prefix = f"TRADING_PROVIDER_{name.upper()}_"

        def positive_float(key: str, default: str) -> float:
            try:
                value = float(os.getenv(prefix + key, default))
            except ValueError as exc:
                raise ValueError(f"{prefix + key} must be numeric") from exc
            if value <= 0:
                raise ValueError(f"{prefix + key} must be > 0")
            return value

        def positive_int(key: str, default: str) -> int:
            try:
                value = int(os.getenv(prefix + key, default))
            except ValueError as exc:
                raise ValueError(f"{prefix + key} must be an integer") from exc
            if value < 1:
                raise ValueError(f"{prefix + key} must be >= 1")
            return value

        enabled = os.getenv(prefix + "ENABLED", "true").strip().lower() in {
            "1", "true", "yes", "on"
        }
        base_url = os.getenv(prefix + "BASE_URL")
        if enabled and not base_url:
            raise ValueError(f"{prefix}BASE_URL is required when provider is enabled")

        return cls(
            name=name,
            api_key=os.getenv(prefix + "API_KEY"),
            api_secret=os.getenv(prefix + "API_SECRET"),
            base_url=base_url,
            timeout_seconds=positive_float("TIMEOUT_SECONDS", "10"),
            rate_limit_per_second=positive_float("RATE_LIMIT_PER_SECOND", "5"),
            retry_attempts=positive_int("RETRY_ATTEMPTS", "3"),
            retry_base_delay_seconds=positive_float("RETRY_BASE_DELAY_SECONDS", "0.25"),
            enabled=enabled,
        )
