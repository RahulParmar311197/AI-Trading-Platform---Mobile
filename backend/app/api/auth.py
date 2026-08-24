from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.auth.security import hash_password, verify_password, create_access_token
from app.db import get_db
from app.models.user import User

router = APIRouter(tags=["auth"])

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=128)

@router.post("/auth/register")
def register(body: Credentials, db: Session = Depends(get_db)):
    username = body.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "user already exists")
    user = User(username=username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(username), "token_type": "bearer"}

@router.post("/auth/login")
def login(body: Credentials, db: Session = Depends(get_db)):
    username = body.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    return {"access_token": create_access_token(username), "token_type": "bearer"}
