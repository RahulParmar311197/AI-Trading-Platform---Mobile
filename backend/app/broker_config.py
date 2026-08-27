from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class BrokerConfigError(ValueError):
    pass


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass(frozen=True)
class BrokerCredentials:
    api_key: str
    api_secret: str
    access_token: str | None = None


@dataclass(frozen=True)
class BrokerConfig:
    name: str
    mode: ExecutionMode
    credentials: BrokerCredentials | None

    @property
    def live_enabled(self) -> bool:
        return self.mode is ExecutionMode.LIVE

    def assert_live_execution_allowed(self) -> None:
        if self.mode is not ExecutionMode.LIVE:
            raise BrokerConfigError("live execution requires broker mode LIVE")
        if self.credentials is None:
            raise BrokerConfigError("LIVE broker credentials are not configured")


def load_broker_config(prefix: str = "BROKER_") -> BrokerConfig:
    """Load canonical environment configuration; PAPER is always the default."""
    raw_mode = os.getenv(prefix + "MODE", "PAPER").strip().upper()
    try:
        mode = ExecutionMode(raw_mode)
    except ValueError as exc:
        raise BrokerConfigError(f"{prefix}MODE must be PAPER or LIVE") from exc

    name = os.getenv(prefix + "NAME", "paper").strip().lower() or "paper"
    if mode is ExecutionMode.PAPER:
        return BrokerConfig(name=name, mode=mode, credentials=None)

    api_key = os.getenv(prefix + "API_KEY", "").strip()
    api_secret = os.getenv(prefix + "API_SECRET", "").strip()
    token = os.getenv(prefix + "ACCESS_TOKEN", "").strip() or None
    if not api_key or not api_secret:
        raise BrokerConfigError("LIVE broker credentials are not configured")
    return BrokerConfig(name=name, mode=mode, credentials=BrokerCredentials(api_key, api_secret, token))


def load_upstox_config() -> BrokerConfig:
    return load_broker_config("UPSTOX_")


def redact(value: str | None) -> str:
    if not value:
        return ""
    return value[:2] + "***" + value[-2:] if len(value) > 4 else "***"
