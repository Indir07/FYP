from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.db import SessionLocal
from app.models import AlertRecord

logger = logging.getLogger("cryptovolt.alerts")

# Fallback ring buffer if DB is unavailable (same process lifetime only).
_recent_alerts: list[dict[str, Any]] = []
_MAX_RECENT = 200
_MAX_DB_ROWS = 5000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _discord_webhook_url() -> Optional[str]:
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        return None
    return url


async def _send_discord(message: str, *, title: str | None = None) -> None:
    url = _discord_webhook_url()
    if not url:
        return

    payload: dict[str, Any] = {
        "content": message,
    }
    if title:
        payload["embeds"] = [{"title": title, "description": message}]

    async with httpx.AsyncClient(timeout=15) as client:
        # Webhook requests should be fire-and-forget; swallow errors.
        try:
            await client.post(url, json=payload)
        except Exception:
            return


def _dispatch_discord(message: str, meta: dict[str, Any] | None) -> None:
    url = _discord_webhook_url()
    if not url:
        return
    title = meta.get("title") if meta else None
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send_discord(message, title=title))
    except RuntimeError:

        def _runner() -> None:
            try:
                asyncio.run(_send_discord(message, title=title))
            except Exception:
                return

        threading.Thread(target=_runner, daemon=True).start()


def _append_memory(alert: dict[str, Any]) -> None:
    _recent_alerts.append(alert)
    if len(_recent_alerts) > _MAX_RECENT:
        del _recent_alerts[: len(_recent_alerts) - _MAX_RECENT]


def _prune_old_rows(db) -> None:
    """Keep table bounded for long-running deployments."""
    try:
        n = db.query(AlertRecord).count()
        if n <= _MAX_DB_ROWS:
            return
        excess = n - _MAX_DB_ROWS + 100
        if excess <= 0:
            return
        oldest = (
            db.query(AlertRecord)
            .order_by(AlertRecord.id.asc())
            .limit(excess)
            .all()
        )
        for row in oldest:
            db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("alert prune failed")


def record_alert(
    *,
    alert_type: str,
    message: str,
    meta: dict[str, Any] | None = None,
    send_to_discord: bool = True,
) -> dict[str, Any]:
    meta = meta or {}
    external_id = f"al_{uuid.uuid4().hex[:12]}"
    ts = _now()

    discord_attempted = bool(send_to_discord and _discord_webhook_url())

    row: AlertRecord | None = None
    try:
        db = SessionLocal()
        try:
            row = AlertRecord(
                external_id=external_id,
                alert_type=alert_type,
                message=message,
                meta=meta or None,
                discord_sent=discord_attempted,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            _prune_old_rows(db)
        finally:
            db.close()
    except Exception:
        logger.exception("Persisting alert to database failed; using in-memory buffer")
        row = None

    alert = {
        "id": external_id,
        "ts": ts,
        "type": alert_type,
        "message": message,
        "meta": meta,
        "discord_sent": discord_attempted,
    }

    if row is not None:
        alert["ts"] = row.created_at.isoformat() if row.created_at else ts

    _append_memory(alert)

    if send_to_discord and discord_attempted:
        _dispatch_discord(message, meta)

    return alert


def list_recent(limit: int = 50) -> list[dict[str, Any]]:
    lim = max(1, min(limit, _MAX_RECENT))
    try:
        db = SessionLocal()
        try:
            rows = (
                db.query(AlertRecord)
                .order_by(AlertRecord.created_at.desc())
                .limit(lim)
                .all()
            )
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "id": r.external_id,
                        "ts": r.created_at.isoformat() if r.created_at else _now(),
                        "type": r.alert_type,
                        "message": r.message,
                        "meta": r.meta or {},
                        "discord_sent": r.discord_sent,
                    }
                )
            return out
        finally:
            db.close()
    except Exception:
        logger.exception("list_recent DB read failed; falling back to memory")

    return list(reversed(_recent_alerts))[-lim:]
