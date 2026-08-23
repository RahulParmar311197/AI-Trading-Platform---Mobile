from __future__ import annotations

import time
from dataclasses import dataclass

from app.data_provider import ProviderError
from app.provider_runtime import ProviderRuntime


@dataclass
class ProviderState:
    failures: int = 0
    opened_until: float = 0.0


class ProviderFailover:
    def __init__(
        self,
        providers: list[ProviderRuntime],
        failure_threshold: int = 3,
        cooldown_seconds: float = 30,
    ):
        if not providers:
            raise ValueError("at least one provider is required")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")

        self.providers = providers
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.states = {p.provider.name: ProviderState() for p in providers}

    def _available(self, runtime: ProviderRuntime) -> bool:
        return time.monotonic() >= self.states[runtime.provider.name].opened_until

    async def historical(self, symbol, start, end, timeframe):
        errors: list[str] = []
        for runtime in self.providers:
            state = self.states[runtime.provider.name]
            if not self._available(runtime):
                continue
            try:
                result = await runtime.historical(symbol, start, end, timeframe)
                state.failures = 0
                state.opened_until = 0.0
                return result
            except Exception as exc:
                state.failures += 1
                errors.append(f"{runtime.provider.name}: {exc}")
                if state.failures >= self.failure_threshold:
                    state.opened_until = time.monotonic() + self.cooldown_seconds

        raise ProviderError("all configured providers failed: " + "; ".join(errors))
