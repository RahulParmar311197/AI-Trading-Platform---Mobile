from app.api.emergency_halt import _require_admin
from fastapi import HTTPException


def test_emergency_halt_auth_requires_bearer():
    try:
        _require_admin(None)
    except HTTPException as exc:
        assert exc.status_code in (401, 503)
    else:
        raise AssertionError("unauthenticated emergency control must be rejected")
