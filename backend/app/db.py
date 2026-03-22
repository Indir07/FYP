from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load repo-root `.env` before reading DATABASE_URL (works for uvicorn, scripts, Alembic).
_repo_root = Path(__file__).resolve().parent.parent.parent
try:
    from dotenv import load_dotenv

    load_dotenv(_repo_root / ".env")
except ImportError:
    pass

# Default: local SQLite next to the backend package (works on Windows/macOS/Linux).
# Set DATABASE_URL in `.env` for PostgreSQL, e.g. postgresql+psycopg2://user:pass@localhost:5432/cryptovolt
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


def ensure_legacy_users_full_name() -> None:
    """
    Legacy `users` tables may use `user_id` and omit `full_name` (auth expects both).
    """
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        if DATABASE_URL.startswith("postgresql"):
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(120) NOT NULL DEFAULT ''"
                )
            )
        else:
            # SQLite: no IF NOT EXISTS on older versions; ignore duplicate column errors
            try:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN full_name VARCHAR(120) NOT NULL DEFAULT ''"
                    )
                )
            except Exception:
                pass

