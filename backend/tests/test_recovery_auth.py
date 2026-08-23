import pytest

from app.api.recovery import _require_recovery_admin
from app.core.config import settings
from app.auth.security import create_access_token


def test_recovery_admin_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "recovery_admin_username", "")
    with pytest.raises(Exception) as exc:
        _require_recovery_admin(None)
    assert getattr(exc.value, "status_code", None) == 503


def test_recovery_admin_rejects_non_admin(monkeypatch):
    monkeypatch.setattr(settings, "recovery_admin_username", "admin")
    credentials = type("Creds", (), {"scheme": "Bearer", "credentials": create_access_token("trader")})()
    with pytest.raises(Exception) as exc:
        _require_recovery_admin(credentials)
    assert getattr(exc.value, "status_code", None) == 403


def test_recovery_admin_accepts_configured_principal(monkeypatch):
    monkeypatch.setattr(settings, "recovery_admin_username", "admin")
    credentials = type("Creds", (), {"scheme": "Bearer", "credentials": create_access_token("admin")})()
    assert _require_recovery_admin(credentials) == "admin"
