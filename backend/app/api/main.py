"""Compatibility ASGI entrypoint.

The canonical FastAPI application lives in :mod:`app.main`.  Keep this
module deliberately thin so legacy deployments importing ``app.api.main``
share the same application instance and lifespan state.
"""

from app.main import app

__all__ = ["app"]
