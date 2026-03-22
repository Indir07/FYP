from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    # Legacy DB uses `user_id` as PK; keep Python attr `id` for the rest of the app.
    id: Mapped[int] = mapped_column("user_id", Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(
        String(120), nullable=False, server_default=""
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PendingUser(Base):
    __tablename__ = "pending_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    verify_code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmailAuthChallenge(Base):
    __tablename__ = "email_auth_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)  # "login"
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    device_label: Mapped[str] = mapped_column(String(120), default="Unknown device", nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AlertRecord(Base):
    """
    Persisted operator/system alerts (audit trail). Discord is optional; rows store
    whether a webhook dispatch was attempted.
    """

    __tablename__ = "alert_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    discord_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

