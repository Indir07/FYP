from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EmailAuthChallenge, PendingUser, User
from app.services.mailer import send_email

router = APIRouter()

pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "cryptovolt-dev-secret")
JWT_ALG = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
VERIFY_CODE_MINUTES = int(os.getenv("AUTH_VERIFY_CODE_MINUTES", "10"))
ALLOW_DEV_OTP_FALLBACK = os.getenv("AUTH_ALLOW_DEV_OTP_FALLBACK", "0").strip() == "1"


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class SignupVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class SignupResendRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email_or_username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    device_label: str = Field(default="Unknown device", max_length=120)


class LoginVerifyRequest(BaseModel):
    challenge_id: int
    code: str = Field(min_length=6, max_length=6)


class LoginResendRequest(BaseModel):
    challenge_id: int


class ForgotPasswordRequest(BaseModel):
    email_or_username: str = Field(min_length=3, max_length=255)


class ResetPasswordConfirmRequest(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


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


def _new_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _send_signup_code(email: str, code: str) -> None:
    send_email(
        to_email=email,
        subject="CryptoVolt signup verification code",
        body=(
            f"Your CryptoVolt signup verification code is: {code}\n\n"
            f"This code expires in {VERIFY_CODE_MINUTES} minutes."
        ),
    )


def _send_login_code(email: str, code: str, device_label: str) -> None:
    send_email(
        to_email=email,
        subject="CryptoVolt login verification code",
        body=(
            f"A login attempt was made from: {device_label}\n\n"
            f"Your CryptoVolt login verification code is: {code}\n\n"
            f"This code expires in {VERIFY_CODE_MINUTES} minutes."
        ),
    )


def _create_reset_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    exp_minutes = int(os.getenv("AUTH_RESET_EXPIRE_MINUTES", "30"))
    payload = {
        "sub": str(user.id),
        "purpose": "reset_password",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _send_reset_link(email: str, token: str) -> None:
    frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    link = f"{frontend_base}/reset-password?token={token}"
    exp_minutes = int(os.getenv("AUTH_RESET_EXPIRE_MINUTES", "30"))
    send_email(
        to_email=email,
        subject="CryptoVolt password reset link",
        body=(
            f"Click the link below to reset your CryptoVolt password:\n\n{link}\n\n"
            f"This link expires in {exp_minutes} minutes."
        ),
    )


@router.post("/signup/request")
def signup_request(req: SignupRequest, db: Session = Depends(get_db)):
    email = req.email.lower().strip()
    username = req.username.strip().lower()
    existing_user = db.query(User).filter(or_(User.email == email, User.username == username)).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already exists.")

    existing_pending = db.query(PendingUser).filter(or_(PendingUser.email == email, PendingUser.username == username)).first()
    if existing_pending:
        db.delete(existing_pending)
        db.commit()

    code = _new_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFY_CODE_MINUTES)
    pending = PendingUser(
        full_name=req.full_name.strip(),
        email=email,
        username=username,
        password_hash=pwd_ctx.hash(req.password),
        verify_code=code,
        expires_at=expires_at,
        consumed=False,
    )
    db.add(pending)
    db.commit()

    try:
        _send_signup_code(email, code)
        return {"message": "Verification code sent to your email."}
    except Exception as exc:
        if ALLOW_DEV_OTP_FALLBACK:
            return {
                "message": "SMTP unavailable; using development OTP fallback.",
                "verification_code": code,
                "expires_in_minutes": VERIFY_CODE_MINUTES,
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send verification email. Please retry in a few seconds.",
        ) from exc


@router.post("/signup/verify", response_model=AuthResponse)
def signup_verify(req: SignupVerifyRequest, db: Session = Depends(get_db)):
    email = req.email.lower().strip()
    pending = db.query(PendingUser).filter(PendingUser.email == email).first()
    if not pending or pending.consumed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending signup found.")
    if pending.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired.")
    if pending.verify_code != req.code.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code.")

    existing_user = db.query(User).filter(or_(User.email == pending.email, User.username == pending.username)).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already exists.")

    user = User(
        full_name=pending.full_name,
        email=pending.email,
        username=pending.username,
        password_hash=pending.password_hash,
    )
    db.add(user)
    pending.consumed = True
    db.commit()
    db.refresh(user)
    token = _create_token(user)
    return AuthResponse(token=token, user={"id": user.id, "full_name": user.full_name, "email": user.email, "username": user.username})


@router.post("/signup/resend")
def signup_resend(req: SignupResendRequest, db: Session = Depends(get_db)):
    email = req.email.lower().strip()
    pending = db.query(PendingUser).filter(PendingUser.email == email, PendingUser.consumed == False).first()  # noqa: E712
    if not pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending signup found.")
    if pending.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signup verification expired. Start signup again.")

    code = _new_code()
    pending.verify_code = code
    pending.expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFY_CODE_MINUTES)
    db.commit()

    try:
        _send_signup_code(pending.email, code)
        return {"message": "Verification code re-sent to your email."}
    except Exception as exc:
        if ALLOW_DEV_OTP_FALLBACK:
            return {
                "message": "SMTP unavailable; using development OTP fallback.",
                "verification_code": code,
                "expires_in_minutes": VERIFY_CODE_MINUTES,
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to resend verification email. Please retry in a few seconds.",
        ) from exc


@router.post("/login/request")
def login_request(req: LoginRequest, db: Session = Depends(get_db)):
    key = req.email_or_username.strip().lower()
    user = db.query(User).filter(or_(User.email == key, User.username == key)).first()
    if not user or not pwd_ctx.verify(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    code = _new_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFY_CODE_MINUTES)
    challenge = EmailAuthChallenge(
        user_id=user.id,
        purpose="login",
        code=code,
        expires_at=expires_at,
        consumed=False,
        device_label=req.device_label.strip()[:120] or "Unknown device",
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    try:
        _send_login_code(user.email, code, challenge.device_label)
        return {"challenge_id": challenge.id, "message": "Verification code sent to your email."}
    except Exception as exc:
        if ALLOW_DEV_OTP_FALLBACK:
            return {
                "challenge_id": challenge.id,
                "message": "SMTP unavailable; using development OTP fallback.",
                "verification_code": code,
                "expires_in_minutes": VERIFY_CODE_MINUTES,
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send login verification email. Please retry in a few seconds.",
        ) from exc


@router.post("/login/verify", response_model=AuthResponse)
def login_verify(req: LoginVerifyRequest, db: Session = Depends(get_db)):
    ch = db.query(EmailAuthChallenge).filter(EmailAuthChallenge.id == req.challenge_id, EmailAuthChallenge.purpose == "login").first()
    if not ch or ch.consumed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid challenge.")
    if ch.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired.")
    if ch.code != req.code.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code.")

    user = db.query(User).filter(User.id == ch.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    ch.consumed = True
    db.commit()

    token = _create_token(user)
    return AuthResponse(token=token, user={"id": user.id, "full_name": user.full_name, "email": user.email, "username": user.username})


@router.post("/login/resend")
def login_resend(req: LoginResendRequest, db: Session = Depends(get_db)):
    ch = db.query(EmailAuthChallenge).filter(
        EmailAuthChallenge.id == req.challenge_id,
        EmailAuthChallenge.purpose == "login",
        EmailAuthChallenge.consumed == False,  # noqa: E712
    ).first()
    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Login challenge not found.")
    if ch.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login verification expired. Login again.")

    user = db.query(User).filter(User.id == ch.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    code = _new_code()
    ch.code = code
    ch.expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFY_CODE_MINUTES)
    db.commit()

    try:
        _send_login_code(user.email, code, ch.device_label)
        return {"message": "Login verification code re-sent to your email."}
    except Exception as exc:
        if ALLOW_DEV_OTP_FALLBACK:
            return {
                "message": "SMTP unavailable; using development OTP fallback.",
                "verification_code": code,
                "expires_in_minutes": VERIFY_CODE_MINUTES,
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to resend login verification email. Please retry in a few seconds.",
        ) from exc


@router.post("/password/forgot")
def password_forgot(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    key = req.email_or_username.strip().lower()
    user = db.query(User).filter(or_(User.email == key, User.username == key)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not registered.")

    token = _create_reset_token(user)
    try:
        _send_reset_link(user.email, token)
        return {"message": "Password reset link sent to your registered email."}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send password reset email. Please retry in a few seconds.",
        ) from exc


@router.post("/password/reset")
def password_reset(req: ResetPasswordConfirmRequest, db: Session = Depends(get_db)):
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match.")
    try:
        payload = jwt.decode(req.token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link.") from exc
    if payload.get("purpose") != "reset_password":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token purpose.")

    sub = str(payload.get("sub", "")).strip()
    if not sub.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token subject.")
    user = db.query(User).filter(User.id == int(sub)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.password_hash = pwd_ctx.hash(req.new_password)
    db.commit()
    return {"message": "Password has been reset successfully."}

