from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

router = APIRouter()

pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "cryptovolt-dev-secret")
JWT_ALG = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email_or_username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: dict


def _create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_EXPIRE_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    existing = (
        db.query(User)
        .filter(or_(User.email == req.email.lower().strip(), User.username == req.username.strip().lower()))
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already exists.")

    user = User(
        full_name=req.full_name.strip(),
        email=req.email.lower().strip(),
        username=req.username.strip().lower(),
        password_hash=pwd_ctx.hash(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = _create_token(user)
    return AuthResponse(
        token=token,
        user={"id": user.id, "full_name": user.full_name, "email": user.email, "username": user.username},
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    key = req.email_or_username.strip().lower()
    user = db.query(User).filter(or_(User.email == key, User.username == key)).first()
    if not user or not pwd_ctx.verify(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    token = _create_token(user)
    return AuthResponse(
        token=token,
        user={"id": user.id, "full_name": user.full_name, "email": user.email, "username": user.username},
    )

