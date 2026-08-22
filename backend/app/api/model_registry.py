from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.model_registry import registry

router = APIRouter(prefix="/api/models", tags=["model-registry"])


class RegisterRequest(BaseModel):
    name: str
    version: str
    metrics: dict


class PromoteRequest(BaseModel):
    name: str
    version: str


@router.post("", status_code=201)
def register(payload: RegisterRequest):
    return registry.register(payload.name, payload.version, payload.metrics).__dict__


@router.post("/promote")
def promote(payload: PromoteRequest):
    try:
        return registry.promote(payload.name, payload.version).__dict__
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
def models():
    return registry.list()
