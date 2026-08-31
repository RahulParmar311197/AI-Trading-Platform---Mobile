from __future__ import annotations

import json
import os

from sqlalchemy.orm import Session

from app.broker_adapter import PaperBrokerAdapter
from app.broker_context_attestation import BrokerContextAttestor
from app.broker_router import BrokerRoute, BrokerRouter
from app.dhan_adapter import DhanAdapter, DhanConfig
from app.models.broker_account import BrokerAccount
from app.risk_reservation_store import RiskReservationStore
from app.security.credential_encryption import decrypt_credentials
from app.safety_state import SafetyStateStore
from app.submission_intent_store import SubmissionIntentStore
from app.upstox_adapter import UpstoxAdapter, UpstoxConfig
from app.reconciliation import ReconciliationEngine


def build_broker_router(
    safety_store: SafetyStateStore | None = None,
    *,
    context_attestor: BrokerContextAttestor | None = None,
    submission_intent_store: SubmissionIntentStore | None = None,
    risk_reservation_store: RiskReservationStore | None = None,
) -> BrokerRouter:
    """Create the configured broker router without making network calls."""
    selected = os.getenv("BROKER_ROUTE", "paper").strip().lower()
    safety = safety_store or SafetyStateStore()
    intents = submission_intent_store or SubmissionIntentStore()
    reconciliation_engine = ReconciliationEngine(
        submission_intent_store=intents,
        state_store=safety,
        risk_reservation_store=risk_reservation_store,
    )
    routes = [BrokerRoute("paper", PaperBrokerAdapter())]

    dhan = DhanAdapter()
    routes.append(BrokerRoute("dhan", dhan, enabled=bool(dhan.config.live_enabled)))

    upstox = UpstoxAdapter()
    routes.append(BrokerRoute("upstox", upstox, enabled=bool(upstox.config.live_enabled)))

    return BrokerRouter(
        routes,
        selected,
        safety_store=safety,
        context_attestor=context_attestor,
        submission_intent_store=intents,
        reconciliation_engine=reconciliation_engine,
    )


def account_route_name(account: BrokerAccount) -> str:
    """Return the canonical route name for a persisted broker account."""
    broker = str(account.broker or "").strip().lower()
    if not broker or account.id is None or int(account.id) <= 0:
        raise ValueError("broker account has invalid route identity")
    return f"{broker}:account:{int(account.id)}"


def account_route_generation(account: BrokerAccount) -> str:
    """Return the persisted version token used to fence stale account routes."""
    if account.id is None or int(account.id) <= 0:
        raise ValueError("broker account has invalid route identity")
    if account.updated_at is None:
        return f"account:{int(account.id)}:bootstrap"
    return f"account:{int(account.id)}:{account.updated_at.isoformat()}"


def _credential_payload(account: BrokerAccount) -> dict:
    try:
        payload = json.loads(decrypt_credentials(account.encrypted_credentials))
    except Exception as exc:
        raise ValueError(f"account:{account.id}:credentials_unreadable") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"account:{account.id}:credentials_must_be_json_object")
    return payload


def build_account_route(account: BrokerAccount) -> BrokerRoute:
    """Build an account-bound adapter from its encrypted credentials."""
    route_name = account_route_name(account)
    generation = account_route_generation(account)
    broker = str(account.broker).strip().lower()
    credentials = _credential_payload(account)

    if broker == "paper":
        adapter = PaperBrokerAdapter()
    elif broker == "upstox":
        access_token = str(credentials.get("access_token", "")).strip()
        if not access_token:
            raise ValueError(f"account:{account.id}:upstox_access_token_missing")
        base_url = str(credentials.get("base_url", "https://api-hft.upstox.com")).rstrip("/")
        adapter = UpstoxAdapter(UpstoxConfig(access_token=access_token, base_url=base_url, live_enabled=True, timeout_seconds=float(credentials.get("timeout_seconds", 10.0)), slice_orders=bool(credentials.get("slice_orders", False)), market_protection=int(credentials.get("market_protection", -1)), broker_account_id=str(account.id), broker_route=route_name, broker_route_generation=generation))
    elif broker == "dhan":
        client_id = str(credentials.get("client_id", "")).strip()
        access_token = str(credentials.get("access_token", "")).strip()
        if not client_id or not access_token:
            raise ValueError(f"account:{account.id}:dhan_credentials_missing")
        base_url = str(credentials.get("base_url", "https://api.dhan.co/v2")).rstrip("/")
        adapter = DhanAdapter(DhanConfig(client_id=client_id, access_token=access_token, base_url=base_url, live_enabled=True, timeout_seconds=float(credentials.get("timeout_seconds", 10.0))))

    else:
        raise ValueError(f"account:{account.id}:unsupported_broker:{broker}")

    return BrokerRoute(route_name, adapter, enabled=True, broker_account_id=int(account.id), generation=generation)


def provision_active_account_routes(db: Session, router: BrokerRouter) -> list[str]:
    """Synchronize account-bound routes to exactly the active persisted accounts."""
    errors: list[str] = []
    with router.route_lifecycle_lock():
        accounts = db.query(BrokerAccount).filter(BrokerAccount.status == "active").order_by(BrokerAccount.id.asc()).all()
        desired_route_names: set[str] = set()
        for account in accounts:
            try:
                desired_route_names.add(account_route_name(account))
            except ValueError as exc:
                errors.append(f"account:{account.id}:invalid_identity:{exc}")

        stale_route_names = [name for name, route in list(router.routes.items()) if route.broker_account_id is not None and name not in desired_route_names]
        for name in stale_route_names:
            router.routes.pop(name, None)

        for account in accounts:
            try:
                route_name = account_route_name(account)
                router.routes.pop(route_name, None)
                route = build_account_route(account)
            except (TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
                errors.append(f"account:{account.id}:provision_failed:{exc}")
                continue
            router.routes[route.name] = route
    return errors


def validate_active_account_routes(db: Session, router: BrokerRouter) -> list[str]:
    """Return fail-closed route-binding errors for every active broker account."""
    errors: list[str] = []
    accounts = db.query(BrokerAccount).filter(BrokerAccount.status == "active").order_by(BrokerAccount.id.asc()).all()
    for account in accounts:
        try:
            route_name = account_route_name(account)
            generation = account_route_generation(account)
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
            continue
        if route.generation != generation:
            errors.append(f"account:{account.id}:{route_name}:route_generation_stale")
    return errors
