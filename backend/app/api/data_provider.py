from fastapi import APIRouter, HTTPException

from app.provider_bootstrap import build_provider_registry


router = APIRouter(
    prefix="/api/providers",
    tags=["data-provider"],
)


@router.get("")
def providers():
    try:
        registry = build_provider_registry()
        return {"providers": registry.names()}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/health")
def provider_health():
    try:
        registry = build_provider_registry()
        return {
            "status": "ok",
            "providers": registry.names(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/{name}/health")
def provider_health_by_name(name: str):
    try:
        registry = build_provider_registry()
        provider = registry.get(name)

        return {
            "provider": provider.name,
            "status": "registered",
        }

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc