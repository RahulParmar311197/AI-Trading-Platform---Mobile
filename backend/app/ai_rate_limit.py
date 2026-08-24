"""Small in-process rate limiter for AI endpoints.

Production deployments should use a shared Redis limiter; this implementation
provides a safe local boundary and avoids unbounded AI-provider spend.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class AIRateLimiter:
    def __init__(self, limit: int = 20, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            cutoff = now - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


ai_rate_limiter = AIRateLimiter()
