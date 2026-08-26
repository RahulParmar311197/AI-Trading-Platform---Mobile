from __future__ import annotations

from threading import RLock

from app.broker_connectivity import BrokerConnectivitySupervisor, ConnectivitySnapshot


class BrokerConnectivityRegistry:
    """Route/account-scoped broker connectivity supervisors."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._supervisors: dict[tuple[int, str], BrokerConnectivitySupervisor] = {}

    @staticmethod
    def _key(broker_account_id: int, broker_route: str) -> tuple[int, str]:
        if int(broker_account_id) <= 0:
            raise ValueError("broker_account_id must be positive")
        route = str(broker_route).strip()
        if not route:
            raise ValueError("broker_route is required")
        return int(broker_account_id), route

    def get(self, broker_account_id: int, broker_route: str) -> BrokerConnectivitySupervisor:
        key = self._key(broker_account_id, broker_route)
        with self._lock:
            supervisor = self._supervisors.get(key)
            if supervisor is None:
                supervisor = BrokerConnectivitySupervisor()
                self._supervisors[key] = supervisor
            return supervisor

    def snapshot(self, broker_account_id: int, broker_route: str) -> ConnectivitySnapshot:
        return self.get(broker_account_id, broker_route).snapshot()

    def remove(self, broker_account_id: int, broker_route: str) -> None:
        key = self._key(broker_account_id, broker_route)
        with self._lock:
            self._supervisors.pop(key, None)
