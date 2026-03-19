from __future__ import annotations

from datetime import datetime

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from app.ml.registry import list_entries
from app.services.binance_market import KlineQuery, fetch_klines
from app.trading.decision import decide
from app.services.alerts_service import record_alert

router = APIRouter()

_state = {"automation": False}


class ToggleResponse(BaseModel):
    automation: bool


class DecisionRequest(BaseModel):
    symbol: str
    interval: str = "1m"
    limit: int = 200
    sentiment_index: float = 0.0
    rules_weight: float = 0.45
    ml_weight: float = 0.55
    veto_threshold: float = -0.35


class DecisionResponse(BaseModel):
    as_of: datetime
    symbol: str
    model_id: str | None
    action: str
    confidence: float
    vetoed: bool
    reason: str


@router.post("/automation/start", response_model=ToggleResponse)
def start():
    _state["automation"] = True
    record_alert(alert_type="SYSTEM", message="Automation started (paper trading).")
    return ToggleResponse(automation=True)


@router.post("/automation/stop", response_model=ToggleResponse)
def stop():
    _state["automation"] = False
    record_alert(alert_type="SYSTEM", message="Automation stopped.")
    return ToggleResponse(automation=False)


@router.get("/automation", response_model=ToggleResponse)
def automation_state():
    return ToggleResponse(automation=bool(_state["automation"]))


@router.post("/decision", response_model=DecisionResponse)
async def decision(req: DecisionRequest):
    # Pick active model (if any)
    entries = list_entries()
    active = next((e for e in entries if e.active), None)
    if active is None and entries:
        active = entries[0]

    df = await fetch_klines(KlineQuery(symbol=req.symbol, interval=req.interval, limit=req.limit))
    if active is None:
        return DecisionResponse(
            as_of=datetime.utcnow(),
            symbol=req.symbol,
            model_id=None,
            action="HOLD",
            confidence=0.0,
            vetoed=False,
            reason="no_model_loaded",
        )

    d = decide(
        model_path=active.artifact_path,
        ohlcv=pd.DataFrame(df),
        sentiment_index=req.sentiment_index,
        rules_weight=req.rules_weight,
        ml_weight=req.ml_weight,
        veto_threshold=req.veto_threshold,
    )

    # Alert only when automation is enabled, to avoid spamming the UI refresh.
    if _state.get("automation"):
        if d.vetoed:
            record_alert(
                alert_type="RISK",
                message=f"Sentiment veto for {req.symbol} ({d.action}) • reason={d.reason}",
                meta={"symbol": req.symbol, "vetoed": True, "reason": d.reason},
            )
        elif d.action in ("BUY", "SELL"):
            record_alert(
                alert_type="SIGNAL",
                message=f"{d.action} {req.symbol} • confidence={d.confidence:.2f} • reason={d.reason}",
                meta={"symbol": req.symbol, "action": d.action, "confidence": d.confidence, "reason": d.reason},
            )
    return DecisionResponse(
        as_of=datetime.utcnow(),
        symbol=req.symbol,
        model_id=active.id,
        action=d.action,
        confidence=d.confidence,
        vetoed=d.vetoed,
        reason=d.reason,
    )

