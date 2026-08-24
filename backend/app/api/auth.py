from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password, create_access_token, needs_password_upgrade
from app.db import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=128)


@router.post("/register")
def register(body: Credentials, db: Session = Depends(get_db)):
    username = body.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "user already exists")
    user = User(username=username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        token = create_access_token(username)
    except RuntimeError as exc:
        raise HTTPException(503, "AUTHENTICATION_NOT_CONFIGURED") from exc
    return {"access_token": token, "token_type": "bearer", "user_id": user.id}


@router.post("/login")
def login(body: Credentials, db: Session = Depends(get_db)):
    username = body.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    if needs_password_upgrade(user.password_hash):
        user.password_hash = hash_password(body.password)
        db.commit()
    try:
        token = create_access_token(username)
    except RuntimeError as exc:
        raise HTTPException(503, "AUTHENTICATION_NOT_CONFIGURED") from exc
    return {"access_token": token, "token_type": "bearer", "user_id": user.id}
