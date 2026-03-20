from __future__ import annotations

import asyncio
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx


_recent_alerts: list[dict[str, Any]] = []
_MAX_RECENT = 200


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


def record_alert(
    *,
    alert_type: str,
    message: str,
    meta: dict[str, Any] | None = None,
    send_to_discord: bool = True,
) -> dict[str, Any]:
    alert = {
        "id": f"al_{uuid.uuid4().hex[:12]}",
        "ts": _now(),
        "type": alert_type,
        "message": message,
        "meta": meta or {},
    }
    _recent_alerts.append(alert)
    if len(_recent_alerts) > _MAX_RECENT:
        del _recent_alerts[: len(_recent_alerts) - _MAX_RECENT]

    # If a Discord webhook is configured, send asynchronously.
    # This function may be called from both async and sync FastAPI endpoints.
    # - In async context: create_task on the running loop.
    # - In sync context: spin a daemon thread and run an event loop there.
    url = _discord_webhook_url()
    if send_to_discord and url:
        title = meta.get("title") if meta else None
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send_discord(message, title=title))
        except RuntimeError:
            def _runner() -> None:
                try:
                    asyncio.run(_send_discord(message, title=title))
                except Exception:
                    # Best-effort: never block alert recording.
                    return

            threading.Thread(target=_runner, daemon=True).start()
    return alert


def list_recent(limit: int = 50) -> list[dict[str, Any]]:
    return list(reversed(_recent_alerts))[: max(1, min(limit, _MAX_RECENT))]

