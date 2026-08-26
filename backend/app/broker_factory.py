from __future__ import annotations

import json
import os

from sqlalchemy.orm import Session

from app.broker_adapter import PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.dhan_adapter import DhanAdapter, DhanConfig
from app.models.broker_account import BrokerAccount
from app.security.credential_encryption import decrypt_credentials
from app.safety_state import SafetyStateStore
from app.upstox_adapter import UpstoxAdapter, UpstoxConfig


def build_broker_router(safety_store: SafetyStateStore | None = None) -> BrokerRouter:
    """Create the configured broker router without making network calls."""
    selected = os.getenv("BROKER_ROUTE", "paper").strip().lower()
    routes = [BrokerRoute("paper", PaperBrokerAdapter())]

    dhan = DhanAdapter()
    routes.append(BrokerRoute("dhan", dhan, enabled=bool(dhan.config.live_enabled)))

    upstox = UpstoxAdapter()
    routes.append(BrokerRoute("upstox", upstox, enabled=bool(upstox.config.live_enabled)))

    return BrokerRouter(routes, selected, safety_store=safety_store or SafetyStateStore())


def account_route_name(account: BrokerAccount) -> str:
    """Return the canonical route name for a persisted broker account."""
    broker = str(account.broker or "").strip().lower()
    if not broker or account.id is None or int(account.id) <= 0:
        raise ValueError("broker account has invalid route identity")
    return f"{broker}:account:{int(account.id)}"


def _credential_payload(account: BrokerAccount) -> dict:
    try:
        payload = json.loads(decrypt_credentials(account.encrypted_credentials))
    except Exception as exc:
        raise ValueError(f"account:{account.id}:credentials_unreadable") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"account:{account.id}:credentials_must_be_json_object")
    return payload


def build_account_route(account: BrokerAccount) -> BrokerRoute:
    """Build an account-bound adapter from its encrypted credentials.

    Account credentials are intentionally not allowed to fall back to global
    environment credentials. Live routes are enabled only after their stored
    credential payload has been validated.
    """
    route_name = account_route_name(account)
    broker = str(account.broker).strip().lower()
    credentials = _credential_payload(account)

    if broker == "paper":
        adapter = PaperBrokerAdapter()
    elif broker == "upstox":
        access_token = str(credentials.get("access_token", "")).strip()
        if not access_token:
            raise ValueError(f"account:{account.id}:upstox_access_token_missing")
        base_url = str(credentials.get("base_url", "https://api-hft.upstox.com")).rstrip("/")
        adapter = UpstoxAdapter(
            UpstoxConfig(
                access_token=access_token,
                base_url=base_url,
                live_enabled=True,
                timeout_seconds=float(credentials.get("timeout_seconds", 10.0)),
                slice_orders=bool(credentials.get("slice_orders", False)),
                market_protection=int(credentials.get("market_protection", -1)),
            )
        )
    elif broker == "dhan":
        client_id = str(credentials.get("client_id", "")).strip()
        access_token = str(credentials.get("access_token", "")).strip()
        if not client_id or not access_token:
            raise ValueError(f"account:{account.id}:dhan_credentials_missing")
        base_url = str(credentials.get("base_url", "https://api.dhan.co/v2")).rstrip("/")
        adapter = DhanAdapter(
            DhanConfig(
                client_id=client_id,
                access_token=access_token,
                base_url=base_url,
                live_enabled=True,
                timeout_seconds=float(credentials.get("timeout_seconds", 10.0)),
            )
        )
    else:
        raise ValueError(f"account:{account.id}:unsupported_broker:{broker}")

    return BrokerRoute(route_name, adapter, enabled=True, broker_account_id=int(account.id))


def provision_active_account_routes(db: Session, router: BrokerRouter) -> list[str]:
    """Provision dedicated adapter routes for every active persisted account."""
    errors: list[str] = []
    accounts = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.status == "active")
        .order_by(BrokerAccount.id.asc())
        .all()
    )
    for account in accounts:
        try:
            route = build_account_route(account)
        except (TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"account:{account.id}:provision_failed:{exc}")
            continue
        router.routes[route.name] = route
    return errors


def validate_active_account_routes(db: Session, router: BrokerRouter) -> list[str]:
    """Return fail-closed route-binding errors for every active broker account."""
    errors: list[str] = []
    accounts = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.status == "active")
        .order_by(BrokerAccount.id.asc())
        .all()
    )
    for account in accounts:
        try:
            route_name = account_route_name(account)
        except ValueError as exc:
            errors.append(f"account:{account.id}:invalid_identity:{exc}")
            continue
        route = router.routes.get(route_name)
        if route is None:
            errors.append(f"account:{account.id}:{route_name}:route_not_registered")
            continue
        if not route.enabled:
            errors.append(f"account:{account.id}:{route_name}:route_disabled")
            continue
        if route.broker_account_id != int(account.id):
            errors.append(f"account:{account.id}:{route_name}:route_account_mismatch")
    return errors
