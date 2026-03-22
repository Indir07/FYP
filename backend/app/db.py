from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Default: local SQLite next to the backend package (works on Windows/macOS/Linux).
# Docker/production should set DATABASE_URL (e.g. postgresql+psycopg2://...).
_default_sqlite = Path(__file__).resolve().parent.parent / "cryptovolt.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_sqlite.as_posix()}")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

