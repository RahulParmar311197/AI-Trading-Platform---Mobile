from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.auth.security import hash_password, verify_password, create_access_token

router = APIRouter(tags=["auth"])

_USERS: dict[str, str] = {}

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=128)

@router.post("/auth/register")
def register(body: Credentials):
    if body.username in _USERS:
        raise HTTPException(409, "user already exists")
    _USERS[body.username] = hash_password(body.password)
    return {"access_token": create_access_token(body.username), "token_type": "bearer"}

@router.post("/auth/login")
def login(body: Credentials):
    stored = _USERS.get(body.username)
    if not stored or not verify_password(body.password, stored):
        raise HTTPException(401, "invalid credentials")
    return {"access_token": create_access_token(body.username), "token_type": "bearer"}
