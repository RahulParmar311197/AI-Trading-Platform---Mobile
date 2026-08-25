from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.execution_health import ExecutionHealth, ExecutionHealthSnapshot


class ExecutionHealthDTO:
    """Stable JSON-safe representation for API/dashboard consumers."""

    @staticmethod
    def from_snapshot(snapshot: ExecutionHealthSnapshot) -> dict[str, Any]:
        return asdict(snapshot)

    @staticmethod
    def current(health: ExecutionHealth) -> dict[str, Any]:
        return ExecutionHealthDTO.from_snapshot(health.snapshot())
