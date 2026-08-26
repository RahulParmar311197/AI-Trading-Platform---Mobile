from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrokerPositionSnapshot:
    """Broker position snapshot with an explicit completeness/authority contract."""

    positions: list[dict[str, Any]]
    complete: bool
    source: str = "broker"
    as_of: float | None = None

    def require_authoritative(self) -> list[dict[str, Any]]:
        if not self.complete:
            raise RuntimeError("broker position snapshot is not authoritative")
        if not isinstance(self.positions, list):
            raise RuntimeError("broker position snapshot is invalid")
        return self.positions
