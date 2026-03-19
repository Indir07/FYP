from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Any

from app.services.alerts_service import list_recent, record_alert, _send_discord

router = APIRouter()


class TestResponse(BaseModel):
    ok: bool
    alert: dict[str, Any]


@router.get("/recent")
def recent(limit: int = 50):
    return {"alerts": list_recent(limit=limit)}


class TestRequest(BaseModel):
    title: str = "CryptoVolt alert test"
    message: str = "If you see this on Discord, webhook + backend alerts are working."
    send_to_discord: bool = True


@router.post("/test", response_model=TestResponse)
async def test_alert(req: TestRequest, bg: BackgroundTasks):
    alert = record_alert(alert_type="SYSTEM", message=req.message, meta={"title": req.title})
    if req.send_to_discord:
        bg.add_task(_send_discord, req.message, title=req.title)
    return TestResponse(ok=True, alert=alert)

